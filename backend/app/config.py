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

    @staticmethod
    def _int_or_none(value: str | None) -> int | None:
        if value is None or value.strip() == "":
            return None
        return int(value)

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"


settings = Settings()
