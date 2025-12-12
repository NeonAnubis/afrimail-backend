"""
Mailcow API Service Client

A comprehensive async client for interacting with the Mailcow API.
Handles mailbox, domain, alias, and quota management operations.
"""

import httpx
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def _safe_int(value, default: int = 0) -> int:
    """Safely convert a value to int, handling strings and None."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


class MailcowError(Exception):
    """Base exception for Mailcow API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)


class MailcowConnectionError(MailcowError):
    """Raised when connection to Mailcow fails."""
    pass


class MailcowAuthError(MailcowError):
    """Raised when authentication fails."""
    pass


class MailcowValidationError(MailcowError):
    """Raised when request validation fails."""
    pass


class MailcowNotFoundError(MailcowError):
    """Raised when a resource is not found."""
    pass


@dataclass
class MailboxInfo:
    """Mailbox information from Mailcow."""
    username: str
    domain: str
    name: str
    quota: int  # bytes
    quota_used: int  # bytes
    active: bool
    messages: int
    last_imap_login: Optional[str] = None
    last_smtp_login: Optional[str] = None
    last_pop3_login: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None

    @property
    def email(self) -> str:
        return f"{self.username}@{self.domain}"

    @property
    def quota_percentage(self) -> float:
        if self.quota == 0:
            return 0.0
        return (self.quota_used / self.quota) * 100


@dataclass
class DomainInfo:
    """Domain information from Mailcow."""
    domain: str
    description: str
    aliases: int
    mailboxes: int
    max_aliases: int
    max_mailboxes: int
    max_quota: int  # bytes per mailbox
    quota: int  # total domain quota in bytes
    quota_used: int  # bytes
    active: bool
    backupmx: bool
    relay_all_recipients: bool
    created: Optional[str] = None
    modified: Optional[str] = None

    @property
    def quota_percentage(self) -> float:
        if self.quota == 0:
            return 0.0
        return (self.quota_used / self.quota) * 100


@dataclass
class AliasInfo:
    """Alias information from Mailcow."""
    id: int
    address: str
    goto: str  # Comma-separated target addresses
    domain: str
    active: bool
    is_catch_all: bool
    created: Optional[str] = None
    modified: Optional[str] = None

    @property
    def target_addresses(self) -> List[str]:
        return [addr.strip() for addr in self.goto.split(",") if addr.strip()]


class MailcowService:
    """
    Async service for interacting with the Mailcow API.

    Mailcow API uses these endpoint patterns:
    - GET /api/v1/get/{resource}/all - List all resources
    - GET /api/v1/get/{resource}/{id} - Get single resource
    - POST /api/v1/add/{resource} - Create resource
    - POST /api/v1/edit/{resource} - Update resource
    - POST /api/v1/delete/{resource} - Delete resource
    """

    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        self.api_url = (api_url or settings.MAILCOW_API_URL).rstrip("/")
        self.api_key = api_key or settings.MAILCOW_API_KEY
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        """Check if Mailcow integration is properly configured."""
        return bool(self.api_url and self.api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                headers={
                    "X-API-Key": self.api_key,
                },
                timeout=30.0,
                verify=True  # SSL verification
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make an API request to Mailcow."""
        if not self.is_configured:
            raise MailcowConnectionError("Mailcow API is not configured")

        client = await self._get_client()
        # Note: MAILCOW_API_URL in .env already includes /api/v1, so we just add the endpoint
        url = f"/{endpoint.lstrip('/')}"

        try:
            if method.upper() == "GET":
                response = await client.get(url, params=params)
            elif method.upper() == "POST":
                response = await client.post(
                    url,
                    json=data,
                    headers={"Content-Type": "application/json"} if data else None
                )
            elif method.upper() == "PUT":
                response = await client.put(
                    url,
                    json=data,
                    headers={"Content-Type": "application/json"} if data else None
                )
            elif method.upper() == "DELETE":
                response = await client.delete(
                    url,
                    json=data,
                    headers={"Content-Type": "application/json"} if data else None
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Log for debugging
            logger.debug(f"Mailcow API {method} {url}: {response.status_code}")

            # Handle response
            if response.status_code == 401:
                raise MailcowAuthError("Invalid API key or unauthorized access")

            if response.status_code == 404:
                raise MailcowNotFoundError(f"Resource not found: {endpoint}")

            # Parse response
            try:
                result = response.json()
            except Exception:
                result = {"raw": response.text}

            # Mailcow returns arrays with status objects like [{"type": "success", "msg": "..."}]
            if isinstance(result, list):
                for item in result:
                    if isinstance(item, dict):
                        if item.get("type") == "error":
                            raise MailcowValidationError(
                                item.get("msg", "Unknown error"),
                                status_code=response.status_code,
                                response_data=result
                            )
                return {"items": result}

            # Check for error responses
            if isinstance(result, dict):
                if result.get("type") == "error":
                    raise MailcowValidationError(
                        result.get("msg", "Unknown error"),
                        status_code=response.status_code,
                        response_data=result
                    )

            return result

        except httpx.ConnectError as e:
            raise MailcowConnectionError(f"Failed to connect to Mailcow: {e}")
        except httpx.TimeoutException as e:
            raise MailcowConnectionError(f"Mailcow request timed out: {e}")
        except MailcowError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in Mailcow request: {e}")
            raise MailcowError(f"Unexpected error: {e}")

    # ==================== Health Check ====================

    async def health_check(self) -> bool:
        """Check if Mailcow API is reachable and authenticated."""
        try:
            await self._request("GET", "get/status/containers")
            return True
        except Exception as e:
            logger.warning(f"Mailcow health check failed: {e}")
            return False

    async def get_status(self) -> Dict[str, Any]:
        """Get Mailcow container status."""
        return await self._request("GET", "get/status/containers")

    # ==================== Domain Management ====================

    async def get_domains(self) -> List[DomainInfo]:
        """Get all domains from Mailcow."""
        result = await self._request("GET", "get/domain/all")
        domains = []

        items = result if isinstance(result, list) else result.get("items", [])
        for item in items:
            if isinstance(item, dict) and "domain_name" in item:
                domains.append(DomainInfo(
                    domain=item.get("domain_name", ""),
                    description=item.get("description", ""),
                    aliases=_safe_int(item.get("aliases_left")),
                    mailboxes=_safe_int(item.get("mboxes_left")),
                    max_aliases=_safe_int(item.get("max_num_aliases_for_domain")),
                    max_mailboxes=_safe_int(item.get("max_num_mboxes_for_domain")),
                    max_quota=_safe_int(item.get("max_quota_for_mbox")),
                    quota=_safe_int(item.get("max_quota_for_domain")),
                    quota_used=_safe_int(item.get("bytes_total")),
                    active=item.get("active", "0") == "1" or item.get("active") == 1,
                    backupmx=item.get("backupmx", "0") == "1" or item.get("backupmx") == 1,
                    relay_all_recipients=item.get("relay_all_recipients", "0") == "1" or item.get("relay_all_recipients") == 1,
                    created=item.get("created"),
                    modified=item.get("modified"),
                ))

        return domains

    async def get_domain(self, domain: str) -> Optional[DomainInfo]:
        """Get a single domain from Mailcow."""
        try:
            result = await self._request("GET", f"get/domain/{domain}")
            if isinstance(result, dict) and "domain_name" in result:
                return DomainInfo(
                    domain=result.get("domain_name", ""),
                    description=result.get("description", ""),
                    aliases=_safe_int(result.get("aliases_left")),
                    mailboxes=_safe_int(result.get("mboxes_left")),
                    max_aliases=_safe_int(result.get("max_num_aliases_for_domain")),
                    max_mailboxes=_safe_int(result.get("max_num_mboxes_for_domain")),
                    max_quota=_safe_int(result.get("max_quota_for_mbox")),
                    quota=_safe_int(result.get("max_quota_for_domain")),
                    quota_used=_safe_int(result.get("bytes_total")),
                    active=result.get("active", "0") == "1" or result.get("active") == 1,
                    backupmx=result.get("backupmx", "0") == "1" or result.get("backupmx") == 1,
                    relay_all_recipients=result.get("relay_all_recipients", "0") == "1" or result.get("relay_all_recipients") == 1,
                    created=result.get("created"),
                    modified=result.get("modified"),
                )
            return None
        except MailcowNotFoundError:
            return None

    async def create_domain(
        self,
        domain: str,
        description: str = "",
        max_aliases: int = 400,
        max_mailboxes: int = 100,
        max_quota_per_mailbox: int = 10737418240,  # 10GB in bytes
        total_quota: int = 107374182400,  # 100GB in bytes
        default_mailbox_quota: int = 5368709120,  # 5GB in bytes
        active: bool = True,
        restart_sogo: bool = True
    ) -> Dict[str, Any]:
        """Create a new domain in Mailcow."""
        data = {
            "domain": domain,
            "description": description,
            "aliases": max_aliases,
            "mailboxes": max_mailboxes,
            "maxquota": max_quota_per_mailbox // (1024 * 1024),  # Convert to MB
            "quota": total_quota // (1024 * 1024),  # Convert to MB
            "defquota": default_mailbox_quota // (1024 * 1024),  # Convert to MB
            "active": "1" if active else "0",
            "restart_sogo": "1" if restart_sogo else "0",
            "backupmx": "0",
            "relay_all_recipients": "0",
            "relay_unknown_only": "0",
            "gal": "1",  # Global Address List
        }

        return await self._request("POST", "add/domain", data=data)

    async def update_domain(
        self,
        domain: str,
        description: Optional[str] = None,
        max_aliases: Optional[int] = None,
        max_mailboxes: Optional[int] = None,
        max_quota_per_mailbox: Optional[int] = None,
        total_quota: Optional[int] = None,
        active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Update an existing domain in Mailcow."""
        data = {
            "items": [domain],
            "attr": {}
        }

        if description is not None:
            data["attr"]["description"] = description
        if max_aliases is not None:
            data["attr"]["aliases"] = max_aliases
        if max_mailboxes is not None:
            data["attr"]["mailboxes"] = max_mailboxes
        if max_quota_per_mailbox is not None:
            data["attr"]["maxquota"] = max_quota_per_mailbox // (1024 * 1024)
        if total_quota is not None:
            data["attr"]["quota"] = total_quota // (1024 * 1024)
        if active is not None:
            data["attr"]["active"] = "1" if active else "0"

        return await self._request("POST", "edit/domain", data=data)

    async def delete_domain(self, domain: str) -> Dict[str, Any]:
        """Delete a domain from Mailcow."""
        return await self._request("POST", "delete/domain", data=[domain])

    # ==================== Mailbox Management ====================

    async def get_mailboxes(self, domain: Optional[str] = None) -> List[MailboxInfo]:
        """Get all mailboxes, optionally filtered by domain."""
        if domain:
            result = await self._request("GET", f"get/mailbox/{domain}")
        else:
            result = await self._request("GET", "get/mailbox/all")

        mailboxes = []
        items = result if isinstance(result, list) else result.get("items", [])

        for item in items:
            if isinstance(item, dict) and "username" in item:
                mailboxes.append(MailboxInfo(
                    username=item.get("local_part", item.get("username", "").split("@")[0]),
                    domain=item.get("domain", ""),
                    name=item.get("name", ""),
                    quota=_safe_int(item.get("quota")),
                    quota_used=_safe_int(item.get("quota_used")),
                    active=item.get("active", "0") == "1" or item.get("active") == 1,
                    messages=_safe_int(item.get("messages")),
                    last_imap_login=item.get("last_imap_login"),
                    last_smtp_login=item.get("last_smtp_login"),
                    last_pop3_login=item.get("last_pop3_login"),
                    created=item.get("created"),
                    modified=item.get("modified"),
                ))

        return mailboxes

    async def get_mailbox(self, email: str) -> Optional[MailboxInfo]:
        """Get a single mailbox by email address."""
        try:
            result = await self._request("GET", f"get/mailbox/{email}")

            # Handle both single object and list responses
            if isinstance(result, list) and len(result) > 0:
                item = result[0]
            elif isinstance(result, dict) and "username" in result:
                item = result
            else:
                return None

            if isinstance(item, dict) and "username" in item:
                return MailboxInfo(
                    username=item.get("local_part", item.get("username", "").split("@")[0]),
                    domain=item.get("domain", ""),
                    name=item.get("name", ""),
                    quota=_safe_int(item.get("quota")),
                    quota_used=_safe_int(item.get("quota_used")),
                    active=item.get("active", "0") == "1" or item.get("active") == 1,
                    messages=_safe_int(item.get("messages")),
                    last_imap_login=item.get("last_imap_login"),
                    last_smtp_login=item.get("last_smtp_login"),
                    last_pop3_login=item.get("last_pop3_login"),
                    created=item.get("created"),
                    modified=item.get("modified"),
                )
            return None
        except MailcowNotFoundError:
            return None

    async def create_mailbox(
        self,
        local_part: str,
        domain: str,
        password: str,
        name: str = "",
        quota: int = 5368709120,  # 5GB in bytes
        active: bool = True,
        force_password_update: bool = False,
        tls_enforce_in: bool = False,
        tls_enforce_out: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new mailbox in Mailcow.

        Args:
            local_part: The username part before @ (e.g., 'john' for john@example.com)
            domain: The domain part (e.g., 'example.com')
            password: The mailbox password
            name: Display name
            quota: Quota in bytes (default 5GB)
            active: Whether mailbox is active
            force_password_update: Force user to change password on first login
            tls_enforce_in: Enforce TLS for incoming mail
            tls_enforce_out: Enforce TLS for outgoing mail
        """
        data = {
            "local_part": local_part,
            "domain": domain,
            "name": name,
            "password": password,
            "password2": password,
            "quota": quota // (1024 * 1024),  # Convert to MB
            "active": "1" if active else "0",
            "force_pw_update": "1" if force_password_update else "0",
            "tls_enforce_in": "1" if tls_enforce_in else "0",
            "tls_enforce_out": "1" if tls_enforce_out else "0",
        }

        return await self._request("POST", "add/mailbox", data=data)

    async def update_mailbox(
        self,
        email: str,
        name: Optional[str] = None,
        quota: Optional[int] = None,
        password: Optional[str] = None,
        active: Optional[bool] = None,
        force_password_update: Optional[bool] = None,
        tls_enforce_in: Optional[bool] = None,
        tls_enforce_out: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Update an existing mailbox in Mailcow."""
        data = {
            "items": [email],
            "attr": {}
        }

        if name is not None:
            data["attr"]["name"] = name
        if quota is not None:
            data["attr"]["quota"] = quota // (1024 * 1024)  # Convert to MB
        if password is not None:
            data["attr"]["password"] = password
            data["attr"]["password2"] = password
        if active is not None:
            data["attr"]["active"] = "1" if active else "0"
        if force_password_update is not None:
            data["attr"]["force_pw_update"] = "1" if force_password_update else "0"
        if tls_enforce_in is not None:
            data["attr"]["tls_enforce_in"] = "1" if tls_enforce_in else "0"
        if tls_enforce_out is not None:
            data["attr"]["tls_enforce_out"] = "1" if tls_enforce_out else "0"

        return await self._request("POST", "edit/mailbox", data=data)

    async def delete_mailbox(self, email: str) -> Dict[str, Any]:
        """Delete a mailbox from Mailcow."""
        return await self._request("POST", "delete/mailbox", data=[email])

    async def update_mailbox_quota(self, email: str, quota_bytes: int) -> Dict[str, Any]:
        """Update mailbox quota."""
        return await self.update_mailbox(email, quota=quota_bytes)

    async def set_mailbox_password(self, email: str, new_password: str) -> Dict[str, Any]:
        """Change mailbox password in Mailcow."""
        return await self.update_mailbox(email, password=new_password)

    async def activate_mailbox(self, email: str) -> Dict[str, Any]:
        """Activate a mailbox."""
        return await self.update_mailbox(email, active=True)

    async def deactivate_mailbox(self, email: str) -> Dict[str, Any]:
        """Deactivate a mailbox (soft disable)."""
        return await self.update_mailbox(email, active=False)

    # ==================== Alias Management ====================

    async def get_aliases(self, domain: Optional[str] = None) -> List[AliasInfo]:
        """Get all aliases, optionally filtered by domain."""
        if domain:
            result = await self._request("GET", f"get/alias/domain/{domain}")
        else:
            result = await self._request("GET", "get/alias/all")

        aliases = []
        items = result if isinstance(result, list) else result.get("items", [])

        for item in items:
            if isinstance(item, dict) and "address" in item:
                address = item.get("address", "")
                aliases.append(AliasInfo(
                    id=_safe_int(item.get("id")),
                    address=address,
                    goto=item.get("goto", ""),
                    domain=item.get("domain", address.split("@")[-1] if "@" in address else ""),
                    active=item.get("active", "0") == "1" or item.get("active") == 1,
                    is_catch_all=address.startswith("@"),
                    created=item.get("created"),
                    modified=item.get("modified"),
                ))

        return aliases

    async def get_alias(self, alias_id: int) -> Optional[AliasInfo]:
        """Get a single alias by ID."""
        try:
            result = await self._request("GET", f"get/alias/{alias_id}")

            if isinstance(result, dict) and "address" in result:
                address = result.get("address", "")
                return AliasInfo(
                    id=_safe_int(result.get("id")),
                    address=address,
                    goto=result.get("goto", ""),
                    domain=result.get("domain", address.split("@")[-1] if "@" in address else ""),
                    active=result.get("active", "0") == "1" or result.get("active") == 1,
                    is_catch_all=address.startswith("@"),
                    created=result.get("created"),
                    modified=result.get("modified"),
                )
            return None
        except MailcowNotFoundError:
            return None

    async def create_alias(
        self,
        address: str,
        goto: str,
        active: bool = True,
        sogo_visible: bool = True
    ) -> Dict[str, Any]:
        """
        Create a new alias in Mailcow.

        Args:
            address: Alias address (e.g., 'alias@example.com' or '@example.com' for catch-all)
            goto: Comma-separated list of target email addresses
            active: Whether alias is active
            sogo_visible: Whether alias is visible in SOGo
        """
        data = {
            "address": address,
            "goto": goto,
            "active": "1" if active else "0",
            "sogo_visible": "1" if sogo_visible else "0",
        }

        return await self._request("POST", "add/alias", data=data)

    async def update_alias(
        self,
        alias_id: int,
        address: Optional[str] = None,
        goto: Optional[str] = None,
        active: Optional[bool] = None,
        sogo_visible: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Update an existing alias in Mailcow."""
        data = {
            "items": [str(alias_id)],
            "attr": {}
        }

        if address is not None:
            data["attr"]["address"] = address
        if goto is not None:
            data["attr"]["goto"] = goto
        if active is not None:
            data["attr"]["active"] = "1" if active else "0"
        if sogo_visible is not None:
            data["attr"]["sogo_visible"] = "1" if sogo_visible else "0"

        return await self._request("POST", "edit/alias", data=data)

    async def delete_alias(self, alias_id: int) -> Dict[str, Any]:
        """Delete an alias from Mailcow."""
        return await self._request("POST", "delete/alias", data=[str(alias_id)])

    async def create_catch_all(self, domain: str, goto: str, active: bool = True) -> Dict[str, Any]:
        """Create a catch-all alias for a domain."""
        return await self.create_alias(f"@{domain}", goto, active)

    # ==================== Resource & Quota Management ====================

    async def get_resource_stats(self) -> Dict[str, Any]:
        """Get overall resource statistics."""
        result = await self._request("GET", "get/resource/all")
        return result

    async def get_mailbox_quota_usage(self, email: str) -> Dict[str, Any]:
        """Get quota usage for a specific mailbox."""
        mailbox = await self.get_mailbox(email)
        if mailbox:
            return {
                "email": mailbox.email,
                "quota": mailbox.quota,
                "quota_used": mailbox.quota_used,
                "quota_percentage": mailbox.quota_percentage,
                "messages": mailbox.messages,
            }
        raise MailcowNotFoundError(f"Mailbox not found: {email}")

    async def get_domain_quota_usage(self, domain: str) -> Dict[str, Any]:
        """Get quota usage for a specific domain."""
        domain_info = await self.get_domain(domain)
        if domain_info:
            return {
                "domain": domain_info.domain,
                "quota": domain_info.quota,
                "quota_used": domain_info.quota_used,
                "quota_percentage": domain_info.quota_percentage,
                "mailboxes": domain_info.mailboxes,
                "max_mailboxes": domain_info.max_mailboxes,
                "aliases": domain_info.aliases,
                "max_aliases": domain_info.max_aliases,
            }
        raise MailcowNotFoundError(f"Domain not found: {domain}")

    # ==================== DKIM Management ====================

    async def get_dkim(self, domain: str) -> Dict[str, Any]:
        """Get DKIM key for a domain."""
        return await self._request("GET", f"get/dkim/{domain}")

    async def create_dkim(
        self,
        domain: str,
        key_length: int = 2048,
        selector: str = "dkim"
    ) -> Dict[str, Any]:
        """Generate DKIM key for a domain."""
        data = {
            "domains": domain,
            "dkim_selector": selector,
            "key_size": key_length,
        }
        return await self._request("POST", "add/dkim", data=data)

    async def delete_dkim(self, domain: str) -> Dict[str, Any]:
        """Delete DKIM key for a domain."""
        return await self._request("POST", "delete/dkim", data=[domain])

    # ==================== Logs & Statistics ====================

    async def get_logs(self, log_type: str = "dovecot", count: int = 100) -> Dict[str, Any]:
        """
        Get logs from Mailcow.

        Args:
            log_type: Type of log (dovecot, postfix, rspamd-history, etc.)
            count: Number of log entries to retrieve
        """
        return await self._request("GET", f"get/logs/{log_type}/{count}")

    async def get_rspamd_stats(self) -> Dict[str, Any]:
        """Get Rspamd statistics."""
        return await self._request("GET", "get/logs/rspamd-stats")

    async def get_quarantine(self) -> Dict[str, Any]:
        """Get quarantined messages."""
        return await self._request("GET", "get/quarantine/all")

    async def get_mail_queue(self) -> Dict[str, Any]:
        """Get mail queue."""
        return await self._request("GET", "get/mailq/all")

    # ==================== Rate Limiting ====================

    async def get_ratelimits(self, mailbox: Optional[str] = None) -> Dict[str, Any]:
        """Get rate limits for a mailbox or all mailboxes."""
        if mailbox:
            return await self._request("GET", f"get/rl-mbox/{mailbox}")
        return await self._request("GET", "get/rl-mbox/all")

    async def set_ratelimit(
        self,
        mailbox: str,
        rate_limit_value: int = 0,
        rate_limit_frame: str = "s"  # s=second, m=minute, h=hour, d=day
    ) -> Dict[str, Any]:
        """
        Set rate limit for a mailbox.

        Args:
            mailbox: Mailbox email address
            rate_limit_value: Number of messages (0 = unlimited)
            rate_limit_frame: Time frame (s/m/h/d)
        """
        data = {
            "items": [mailbox],
            "attr": {
                "rl_value": rate_limit_value,
                "rl_frame": rate_limit_frame,
            }
        }
        return await self._request("POST", "edit/rl-mbox", data=data)

    # ==================== Sync Operations ====================

    async def sync_mailbox_to_db(self, email: str, db_session) -> Optional[Dict[str, Any]]:
        """
        Sync a mailbox from Mailcow to the local database.
        Updates MailboxMetadata with current quota information.
        """
        from app.models.mailbox import MailboxMetadata
        from sqlalchemy import select

        mailbox = await self.get_mailbox(email)
        if not mailbox:
            return None

        # Update local database
        result = await db_session.execute(
            select(MailboxMetadata).where(MailboxMetadata.email == email)
        )
        metadata = result.scalar_one_or_none()

        if metadata:
            metadata.quota_bytes = mailbox.quota
            metadata.usage_bytes = mailbox.quota_used
        else:
            metadata = MailboxMetadata(
                email=email,
                quota_bytes=mailbox.quota,
                usage_bytes=mailbox.quota_used,
            )
            db_session.add(metadata)

        await db_session.commit()
        await db_session.refresh(metadata)

        return {
            "email": email,
            "quota_bytes": metadata.quota_bytes,
            "usage_bytes": metadata.usage_bytes,
            "quota_used_percentage": metadata.quota_used_percentage,
        }


# Global service instance
mailcow_service = MailcowService()
