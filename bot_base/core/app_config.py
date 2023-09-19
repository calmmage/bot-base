from typing import Type

from pydantic import model_validator
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseSettings):
    conn_str: str
    name: str

    model_config = {
        "extra": "ignore",
        "env_prefix": "DATABASE_",
    }


class TelegramBotConfig(BaseSettings):
    token: str

    send_long_messages_as_files: bool = True
    test_mode: bool = False

    model_config = {
        "extra": "ignore",
        "env_prefix": "TELEGRAM_BOT_",
    }


class AppConfig(BaseSettings):
    _database_config_class: Type[DatabaseConfig] = DatabaseConfig
    _telegram_bot_config_class: Type[TelegramBotConfig] = TelegramBotConfig

    database: DatabaseConfig
    telegram_bot: TelegramBotConfig
    openai_api_key: str

    @model_validator(mode="before")
    @classmethod
    def populate_configurations(cls, values):
        db_class = values.get("_database_config_class", DatabaseConfig)
        tg_class = values.get("_telegram_bot_config_class", TelegramBotConfig)

        values["database"] = db_class(**values)
        values["telegram_bot"] = tg_class(**values)
        return values
