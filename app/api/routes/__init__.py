from fastapi import APIRouter
from app.api.routes import auth, users, admin, admin_users, admin_groups, admin_aliases
from app.api.routes import admin_announcements, admin_support, admin_domains
from app.api.routes import admin_templates, admin_scheduled, admin_sending, admin_storage
from app.api.routes import admin_activity, admin_audit, admin_mailcow

# Public API router (matches /api endpoint from frontend)
api_router = APIRouter()

# Auth routes
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# User routes
api_router.include_router(users.router, prefix="/user", tags=["User"])

# Announcements for users
api_router.include_router(admin_announcements.public_router, prefix="/announcements", tags=["Announcements"])

# Admin API router (matches /admin endpoint from frontend)
admin_router = APIRouter()

# Admin authentication
admin_router.include_router(admin.router, tags=["Admin"])

# Admin management routes
admin_router.include_router(admin_users.router, prefix="/users", tags=["Admin - Users"])
admin_router.include_router(admin_groups.router, prefix="/groups", tags=["Admin - Groups"])
admin_router.include_router(admin_aliases.router, prefix="/aliases", tags=["Admin - Aliases"])
admin_router.include_router(admin_announcements.router, prefix="/announcements", tags=["Admin - Announcements"])
admin_router.include_router(admin_support.router, prefix="/support", tags=["Admin - Support"])
admin_router.include_router(admin_domains.router, prefix="/domains", tags=["Admin - Domains"])
admin_router.include_router(admin_templates.router, prefix="/templates", tags=["Admin - Templates"])
admin_router.include_router(admin_scheduled.router, prefix="/scheduled-actions", tags=["Admin - Scheduled Actions"])
admin_router.include_router(admin_sending.router, prefix="/sending-limits", tags=["Admin - Sending Limits"])
admin_router.include_router(admin_storage.router, prefix="/storage", tags=["Admin - Storage"])
admin_router.include_router(admin_activity.router, prefix="/activity", tags=["Admin - Activity"])
admin_router.include_router(admin_audit.router, prefix="/audit-logs", tags=["Admin - Audit Logs"])

# Admin users and roles management
admin_router.include_router(admin.admins_router, prefix="/admins", tags=["Admin - Admin Users"])
admin_router.include_router(admin.roles_router, prefix="/roles", tags=["Admin - Roles"])

# Stats endpoint
admin_router.include_router(admin.stats_router, tags=["Admin - Stats"])

# Mailcow management routes
admin_router.include_router(admin_mailcow.router, prefix="/mailcow", tags=["Admin - Mailcow"])
