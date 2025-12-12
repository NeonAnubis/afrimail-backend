#!/usr/bin/env python3
"""
Initialize the database with tables and default data.
Run this script to set up a fresh database.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.session import engine, AsyncSessionLocal
from app.models import *  # Import all models
from app.core.security import get_password_hash


async def init_database():
    """Initialize database with all tables."""
    print("Initializing database...")

    async with engine.begin() as conn:
        # Create all tables
        from app.db.session import Base
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created successfully.")


async def create_default_admin():
    """Create a default admin user if none exists."""
    print("Checking for default admin...")

    async with AsyncSessionLocal() as session:
        # Check if any admin exists
        result = await session.execute(
            text("SELECT COUNT(*) FROM admin_users")
        )
        count = result.scalar()

        if count == 0:
            print("Creating default admin user...")

            # First, check/create Super Admin role
            role_result = await session.execute(
                text("SELECT id FROM admin_roles WHERE name = 'Super Admin' LIMIT 1")
            )
            role_row = role_result.first()

            if not role_row:
                # Create the role
                await session.execute(
                    text("""
                        INSERT INTO admin_roles (name, description, permissions, is_system_role)
                        VALUES (
                            'Super Admin',
                            'Full system access with all permissions',
                            '{"users": {"view": true, "create": true, "edit": true, "delete": true, "suspend": true}}'::jsonb,
                            true
                        )
                    """)
                )
                await session.commit()

                role_result = await session.execute(
                    text("SELECT id FROM admin_roles WHERE name = 'Super Admin' LIMIT 1")
                )
                role_row = role_result.first()

            role_id = role_row[0] if role_row else None

            # Create default admin
            password_hash = get_password_hash("admin123")
            await session.execute(
                text("""
                    INSERT INTO admin_users (email, password_hash, name, role_id, is_active)
                    VALUES (:email, :password_hash, :name, :role_id, true)
                """),
                {
                    "email": "admin@afrimail.com",
                    "password_hash": password_hash,
                    "name": "System Administrator",
                    "role_id": role_id
                }
            )
            await session.commit()
            print("Default admin created:")
            print("  Email: admin@afrimail.com")
            print("  Password: admin123")
            print("  ⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")
        else:
            print(f"Found {count} existing admin(s). Skipping default admin creation.")


async def create_default_settings():
    """Create default system settings."""
    print("Creating default settings...")

    async with AsyncSessionLocal() as session:
        settings_data = [
            (
                "quota_presets",
                '{"presets": [{"name": "Basic", "value": 1073741824}, {"name": "Standard", "value": 5368709120}, {"name": "Premium", "value": 10737418240}, {"name": "Business", "value": 26843545600}]}',
                "Default quota presets in bytes"
            ),
            (
                "maintenance_mode",
                '{"enabled": false, "message": "System maintenance in progress. Please try again later."}',
                "Maintenance mode configuration"
            ),
            (
                "default_user_quota",
                '{"value": 5368709120}',
                "Default quota for new users in bytes (5GB)"
            )
        ]

        for key, value, desc in settings_data:
            try:
                await session.execute(
                    text("""
                        INSERT INTO system_settings (setting_key, setting_value, description)
                        VALUES (:key, :value::jsonb, :desc)
                        ON CONFLICT (setting_key) DO NOTHING
                    """),
                    {"key": key, "value": value, "desc": desc}
                )
            except Exception as e:
                print(f"  Warning: Could not create setting {key}: {e}")

        await session.commit()
        print("Default settings created.")


async def create_default_domain():
    """Create default mail domain."""
    print("Creating default domain...")

    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                text("""
                    INSERT INTO mail_domains (domain, is_primary, is_active, description)
                    VALUES ('afrimail.com', true, true, 'Primary mail domain for Afrimail service')
                    ON CONFLICT (domain) DO NOTHING
                """)
            )
            await session.commit()
            print("Default domain 'afrimail.com' created.")
        except Exception as e:
            print(f"  Warning: Could not create default domain: {e}")


async def main():
    """Run all initialization steps."""
    print("=" * 50)
    print("Afrimail Database Initialization")
    print("=" * 50)

    try:
        await init_database()
        await create_default_admin()
        await create_default_settings()
        await create_default_domain()

        print("=" * 50)
        print("Database initialization complete!")
        print("=" * 50)
    except Exception as e:
        print(f"Error during initialization: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
