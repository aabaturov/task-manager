import os


class Settings:
    def __init__(self) -> None:
        self.database_path = os.environ.get("DATABASE_PATH", "/data/app.db")
        self.secret_key = os.environ.get("SECRET_KEY", "dev-insecure-secret-change-me")
        self.web_login = os.environ.get("WEB_LOGIN", "admin")
        self.web_password = os.environ.get("WEB_PASSWORD", "admin")
        self.telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.telegram_allowed_user_id = self._int_or_none(
            os.environ.get("TELEGRAM_ALLOWED_USER_ID")
        )
        # SPEC-004 Feature 3/4: a single application timezone used to interpret
        # event dates and to schedule the bot's "day before" reminders.
        self.timezone = os.environ.get("APP_TIMEZONE", "UTC")
        # Time of day (HH:MM, app timezone) when the bot sends the reminder for
        # the next day's events.
        self.reminder_time = os.environ.get("REMINDER_TIME", "20:00")

    @staticmethod
    def _int_or_none(value: str | None) -> int | None:
        if value is None or value.strip() == "":
            return None
        return int(value)

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"


settings = Settings()
