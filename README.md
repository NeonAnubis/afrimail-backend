# Afrimail Backend API

A high-performance, async FastAPI backend for **Afrimail** - Africa's Continental Email Platform.

---

## Overview

This backend provides a comprehensive REST API for managing email services, user accounts, admin operations, and system configuration. Built with modern Python technologies for scalability and performance.

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| **FastAPI** | 0.109.2 | Web framework |
| **SQLAlchemy** | 2.0.25 | ORM with async support |
| **PostgreSQL** | 14+ | Database |
| **asyncpg** | 0.29.0 | Async PostgreSQL driver |
| **Pydantic** | 2.6.1 | Data validation |
| **python-jose** | 3.3.0 | JWT authentication |
| **passlib** | 1.7.4 | Password hashing (bcrypt) |
| **httpx** | 0.26.0 | Async HTTP client (Mailcow API) |
| **argon2-cffi** | 23.1.0 | Password hashing (Argon2id) |

---

## Mailcow Integration

This backend integrates directly with the Mailcow mail server API for managing email accounts, domains, and related operations.

### Features

- **Health Monitoring**: Real-time status of Mailcow containers
- **Mailbox Management**: Create, update, delete, activate/deactivate mailboxes
- **Domain Management**: Full CRUD operations with quota management
- **Alias Management**: Email forwarding and catch-all aliases
- **DKIM Management**: View, generate, and delete DKIM keys
- **Logs & Monitoring**: Dovecot, Postfix, and Rspamd logs
- **Queue Management**: View mail queue and quarantined messages
- **Rate Limiting**: Configure sending rate limits per mailbox
- **Sync Operations**: Synchronize mailbox data between Mailcow and local database

### Configuration

Add these variables to your `.env` file:

```env
# Mailcow API Configuration
MAILCOW_API_URL=https://mail.yourdomain.com/api/v1
MAILCOW_API_KEY=your-mailcow-api-key
```

**Important**: The `MAILCOW_API_URL` should include `/api/v1` as shown above.

### Required Mailcow API Permissions

Your API key needs these permissions:
- Read/Write mailboxes
- Read/Write domains
- Read/Write aliases
- Read/Write DKIM
- Read logs
- Read/Write rate limits

---

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── deps/               # Dependency injection
│   │   │   └── auth.py         # Authentication dependencies
│   │   └── routes/             # API route handlers
│   │       ├── auth.py                 # User authentication
│   │       ├── users.py                # User operations
│   │       ├── admin.py                # Admin auth & management
│   │       ├── admin_users.py          # User management (admin)
│   │       ├── admin_groups.py         # Group management
│   │       ├── admin_aliases.py        # Email alias management
│   │       ├── admin_domains.py        # Domain management
│   │       ├── admin_mailcow.py        # Mailcow API integration
│   │       ├── admin_storage.py        # Storage & quota management
│   │       ├── admin_sending.py        # Sending limits
│   │       ├── admin_templates.py      # User templates
│   │       ├── admin_scheduled.py      # Scheduled actions
│   │       ├── admin_announcements.py  # System announcements
│   │       ├── admin_support.py        # Support tickets
│   │       ├── admin_activity.py       # Login activity logs
│   │       └── admin_audit.py          # Audit logs
│   ├── core/
│   │   ├── config.py           # Application settings
│   │   └── security.py         # Security utilities (JWT, hashing)
│   ├── db/
│   │   ├── session.py          # Database session management
│   │   └── __init__.py
│   ├── models/                 # SQLAlchemy models
│   │   ├── user.py             # User model
│   │   ├── admin.py            # Admin user & roles
│   │   ├── mailbox.py          # Mailbox metadata
│   │   ├── domain.py           # Mail domains
│   │   ├── alias.py            # Email aliases
│   │   ├── group.py            # User groups
│   │   ├── template.py         # User templates
│   │   ├── sending.py          # Sending tiers & limits
│   │   ├── scheduled.py        # Scheduled actions
│   │   ├── support.py          # Support tickets
│   │   ├── audit.py            # Audit & activity logs
│   │   ├── signup.py           # Signup attempts & password resets
│   │   └── settings.py         # System settings
│   ├── schemas/                # Pydantic schemas
│   │   ├── auth.py             # Auth request/response schemas
│   │   ├── user.py             # User schemas
│   │   ├── admin.py            # Admin schemas
│   │   └── common.py           # Shared schemas
│   ├── services/               # External service integrations
│   │   └── mailcow.py          # Mailcow API client
│   └── main.py                 # Application entry point
├── scripts/
│   ├── init_db.py              # Database initialization script
│   └── migrate_schema.sql      # SQL migration script
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- pip (Python package manager)

### Installation

1. **Navigate to the backend directory**
   ```bash
   cd backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate     # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize database**

   Tables are automatically created on first run, or you can manually initialize:
   ```bash
   python scripts/init_db.py
   ```

6. **Run the server**
   ```bash
   # Development (with hot reload)
   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

   # Production
   uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4
   ```

---

## Environment Variables

Create a `.env` file with the following variables:

```env
# Database Configuration
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=afrimail
DATABASE_PASSWORD=your_secure_password
DATABASE_NAME=afrimail_db
DATABASE_URL=postgresql+asyncpg://afrimail:your_secure_password@localhost:5432/afrimail_db

# JWT Configuration
JWT_SECRET=your-super-secret-jwt-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# hCaptcha (for signup protection)
HCAPTCHA_SITE_KEY=your_hcaptcha_site_key
HCAPTCHA_SECRET_KEY=your_hcaptcha_secret_key

# Rate Limiting
RATE_LIMIT_SIGNUPS_PER_HOUR=5
RATE_LIMIT_SIGNUPS_PER_DAY=10

# CORS Configuration (JSON array)
CORS_ORIGINS=["http://localhost:5173","https://yourdomain.com"]

# Application
DEBUG=true
APP_NAME=Afrimail API
APP_VERSION=1.0.0
```

---

## API Endpoints

### Health Check

```bash
curl http://localhost:8001/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

### Public API (`/api`)

#### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/signup` | Register new user |
| `POST` | `/api/auth/login` | User login |
| `GET` | `/api/auth/me` | Get current user |
| `GET` | `/api/auth/check-username/{username}` | Check username availability |
| `POST` | `/api/auth/forgot-password` | Request password reset |
| `POST` | `/api/auth/verify-otp` | Verify OTP code |
| `POST` | `/api/auth/reset-password` | Reset password |

#### User Operations
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/user/profile` | Get user profile |
| `PUT` | `/api/user/profile` | Update profile |
| `POST` | `/api/user/password` | Change password |
| `GET` | `/api/user/mailbox-info` | Get mailbox info |

#### Public Resources
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/announcements` | Get active announcements |

### Admin API (`/admin`)

#### Admin Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/admin/login` | Admin login |
| `GET` | `/admin/auth/me` | Get current admin |
| `GET` | `/admin/stats` | Dashboard statistics |

#### User Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin/users` | List all users |
| `GET` | `/admin/users/{id}` | Get user details |
| `POST` | `/admin/users` | Create user |
| `PUT` | `/admin/users/{id}` | Update user |
| `DELETE` | `/admin/users/{id}` | Delete user |
| `PUT` | `/admin/users/{email}/suspend` | Suspend user |
| `PUT` | `/admin/users/{email}/unsuspend` | Unsuspend user |
| `PUT` | `/admin/users/{email}/quota` | Update user quota |

#### Domain Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin/domains` | List domains |
| `POST` | `/admin/domains/add` | Add domain |
| `PUT` | `/admin/domains/{id}` | Update domain |
| `DELETE` | `/admin/domains/{id}` | Delete domain |

#### Storage Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin/storage` | Storage overview |
| `GET` | `/admin/storage/stats` | Storage statistics |
| `GET` | `/admin/storage/presets` | Quota presets |

#### Group Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin/groups` | List groups |
| `POST` | `/admin/groups` | Create group |
| `PUT` | `/admin/groups/{id}` | Update group |
| `DELETE` | `/admin/groups/{id}` | Delete group |

#### Email Aliases
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin/aliases` | List aliases |
| `POST` | `/admin/aliases` | Create alias |
| `DELETE` | `/admin/aliases/{id}` | Delete alias |

#### Admin User Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin/admins` | List admin users |
| `POST` | `/admin/admins` | Create admin |
| `PUT` | `/admin/admins/{id}` | Update admin |
| `DELETE` | `/admin/admins/{id}` | Delete admin |

#### Roles Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin/roles` | List roles |
| `POST` | `/admin/roles` | Create role |
| `PUT` | `/admin/roles/{id}` | Update role |
| `DELETE` | `/admin/roles/{id}` | Delete role |

#### Mailcow Integration (`/admin/mailcow`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin/mailcow/health` | Check Mailcow API connectivity |
| `GET` | `/admin/mailcow/status` | Get container status |
| `GET` | `/admin/mailcow/mailboxes` | List all Mailcow mailboxes |
| `GET` | `/admin/mailcow/mailboxes/{email}` | Get mailbox details |
| `POST` | `/admin/mailcow/mailboxes/{email}/activate` | Activate mailbox |
| `POST` | `/admin/mailcow/mailboxes/{email}/deactivate` | Deactivate mailbox |
| `PUT` | `/admin/mailcow/mailboxes/{email}/quota` | Update mailbox quota |
| `POST` | `/admin/mailcow/mailboxes/bulk` | Bulk mailbox operations |
| `POST` | `/admin/mailcow/sync/mailboxes` | Sync all mailboxes to DB |
| `POST` | `/admin/mailcow/sync/mailbox/{email}` | Sync single mailbox |
| `GET` | `/admin/mailcow/dkim/{domain}` | Get DKIM key for domain |
| `POST` | `/admin/mailcow/dkim/{domain}` | Generate DKIM key |
| `GET` | `/admin/mailcow/logs/{log_type}` | View mail server logs |
| `GET` | `/admin/mailcow/stats/rspamd` | Get Rspamd statistics |
| `GET` | `/admin/mailcow/quarantine` | View quarantined messages |
| `GET` | `/admin/mailcow/mail-queue` | View mail queue |
| `GET` | `/admin/mailcow/ratelimits` | List all rate limits |
| `PUT` | `/admin/mailcow/ratelimits/{mailbox}` | Set mailbox rate limit |

#### Other Admin Endpoints
| Prefix | Description |
|--------|-------------|
| `/admin/announcements` | System announcements management |
| `/admin/support` | Support ticket management |
| `/admin/templates` | User provisioning templates |
| `/admin/scheduled-actions` | Scheduled operations |
| `/admin/sending-limits` | Email sending rate limits |
| `/admin/activity` | Login activity logs |
| `/admin/audit-logs` | System audit logs |

---

## Authentication

The API uses JWT (JSON Web Tokens) for authentication.

### Token Structure

```json
{
  "sub": "user@example.com",
  "is_admin": false,
  "exp": 1234567890
}
```

### Using Authentication

Include the JWT token in the `Authorization` header:

```
Authorization: Bearer <your_jwt_token>
```

### User vs Admin Authentication

- **User tokens** (`is_admin: false`): Access `/api/*` endpoints
- **Admin tokens** (`is_admin: true`): Access `/admin/*` endpoints

---

## Database Models

### Core Models

| Model | Description |
|-------|-------------|
| **User** | End-user accounts |
| **AdminUser** | Administrator accounts |
| **AdminRole** | Role-based permissions |
| **MailDomain** | Email domains |
| **MailboxMetadata** | User mailbox info & quotas |
| **EmailAlias** | Email forwarding aliases |

### Supporting Models

| Model | Description |
|-------|-------------|
| **UserGroup** / **UserGroupMember** | Group management |
| **UserTemplate** | User provisioning templates |
| **SendingTier** / **EmailSendingLimit** | Rate limiting |
| **SupportTicket** | Help desk system |
| **Announcement** | System notifications |
| **AuditLog** / **LoginActivity** | Security logging |
| **SignupAttempt** / **PasswordReset** | Auth tracking |
| **SystemSettings** | Configuration storage |

---

## Security Features

| Feature | Description |
|---------|-------------|
| **Password Hashing** | bcrypt with automatic salting |
| **JWT Authentication** | Secure token-based auth with expiration |
| **hCaptcha Integration** | Bot protection on signup |
| **Rate Limiting** | Configurable signup limits per hour/day |
| **CORS Protection** | Whitelist-based origin control |
| **Input Validation** | Pydantic schema validation |
| **SQL Injection Prevention** | SQLAlchemy ORM parameterized queries |

---

## API Documentation

When running in debug mode (`DEBUG=true`), interactive API documentation is available:

- **Swagger UI**: `http://localhost:8001/docs`
- **ReDoc**: `http://localhost:8001/redoc`

---

## Creating an Admin User

After initializing the database, create your first admin user:

```bash
python -c "
import asyncio
from app.core.security import get_password_hash
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def create_admin():
    async with AsyncSessionLocal() as session:
        pwd = get_password_hash('your-secure-password')
        await session.execute(text('''
            INSERT INTO admin_users (email, password_hash, name, is_active)
            VALUES ('admin@afrimail.com', :pwd, 'Administrator', true)
            ON CONFLICT (email) DO UPDATE SET password_hash = :pwd
        '''), {'pwd': pwd})
        await session.commit()
        print('Admin created successfully!')

asyncio.run(create_admin())
"
```

---

## Frontend Integration

Configure the frontend to connect to this backend:

1. Create/update `.env` in the frontend root:
   ```env
   VITE_API_URL=http://localhost:8001
   ```

2. The frontend's `ApiClient` will automatically use this URL for API requests.

---

## Production Deployment

### Recommended Setup

- **Reverse Proxy**: Nginx or Traefik
- **Process Manager**: systemd or supervisor
- **SSL**: Let's Encrypt certificates
- **Database**: PostgreSQL with connection pooling (PgBouncer)

### Production Checklist

- [ ] Set `DEBUG=false` in `.env`
- [ ] Use strong, unique `JWT_SECRET`
- [ ] Configure proper `CORS_ORIGINS`
- [ ] Enable HTTPS via reverse proxy
- [ ] Set up database backups
- [ ] Configure log rotation
- [ ] Use environment variables (don't commit `.env`)

### Example systemd Service

```ini
[Unit]
Description=Afrimail API
After=network.target postgresql.service

[Service]
User=afrimail
Group=afrimail
WorkingDirectory=/opt/afrimail/backend
Environment="PATH=/opt/afrimail/backend/venv/bin"
ExecStart=/opt/afrimail/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Gunicorn Alternative

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8001
```

---

## Development

### Running Tests

```bash
pytest
```

### Code Style

- Follow PEP 8 guidelines
- Use type hints for all function parameters and return values
- Document complex functions with docstrings

### Adding New Routes

1. Create route file in `app/api/routes/`
2. Define router with appropriate tags
3. Register in `app/api/routes/__init__.py`
4. Add Pydantic schemas in `app/schemas/` if needed
5. Add SQLAlchemy models in `app/models/` if needed

---

## Troubleshooting

### Common Issues

**Port already in use**
```bash
lsof -ti:8001 | xargs -r kill -9
```

**Database connection errors**
- Verify PostgreSQL is running
- Check credentials in `.env`
- Ensure database exists

**CORS errors**
- Verify frontend URL is in `CORS_ORIGINS`
- Ensure the format is a valid JSON array

**JWT errors**
- Check `JWT_SECRET` is set
- Verify token hasn't expired

**Mailcow API errors (500)**
- Verify `MAILCOW_API_URL` includes `/api/v1` (e.g., `https://mail.example.com/api/v1`)
- Don't add duplicate `/api/v1` - the service adds endpoints directly to this base URL
- Check that the API key has correct permissions
- Ensure the Mailcow server is accessible from the backend

**Mailcow TypeError (str/int division)**
- The Mailcow API returns strings for numeric fields
- The `_safe_int()` helper in `services/mailcow.py` handles type conversion
- If you see this error, ensure all numeric fields use `_safe_int()`

**Mailcow connection refused**
- Verify Mailcow server URL is correct
- Check firewall rules allow outbound HTTPS connections
- Ensure SSL certificate is valid (or set `verify=False` for testing)

---

## License

Proprietary - All rights reserved.

## Support

For issues or questions, please contact the development team.
