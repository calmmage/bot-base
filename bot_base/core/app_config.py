from pydantic import SecretStr
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseSettings):
    conn_str: SecretStr = SecretStr("")
    name: str = ""

    model_config = {
        "env_prefix": "DATABASE_",
    }


class TelegramBotConfig(BaseSettings):
    token: SecretStr = SecretStr("")

    send_long_messages_as_files: bool = True
    test_mode: bool = False
    allowed_users: list = []

    model_config = {
        "env_prefix": "TELEGRAM_BOT_",
    }


class AppConfig(BaseSettings):
    database: DatabaseConfig = DatabaseConfig()
    telegram_bot: TelegramBotConfig = TelegramBotConfig()
    openai_api_key: SecretStr
    process_audio_in_parallel: bool = False
