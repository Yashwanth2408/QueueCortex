from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    trinity_mcp_url: str
    trinity_mcp_token: str

    db_path: str = "./data/tracker.db"
    host: str = "127.0.0.1"
    port: int = 8000

    tracked_agent_email: str = "yashwanth.balaji@emergent.sh"
    poll_interval_minutes: int = 20
    reporting_timezone: str = "Asia/Kolkata"

    trinity_ticket_url_template: str = "https://trinity-base.internal.emergent.host/tickets/{id}"

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Auth: single-user email+OTP login. allowed_login_email defaults to
    # tracked_agent_email when blank - this app is scoped to one agent.
    allowed_login_email: str = ""
    session_secret: str = "queuecortex-dev-secret-change-me"
    session_ttl_days: int = 7
    otp_ttl_minutes: int = 5

    # SMTP for sending OTP emails. If smtp_user/smtp_password are blank (or
    # sending fails), the OTP is returned directly in the API response
    # instead, so login isn't blocked while email delivery gets configured.
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    @property
    def resolved_allowed_login_email(self) -> str:
        return (self.allowed_login_email or self.tracked_agent_email).lower()

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
