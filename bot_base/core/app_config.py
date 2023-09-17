from typing import Type

from pydantic_settings import BaseSettings


class DatabaseConfig(BaseSettings):
    conn_str: str
    name: str

    class Config:
        env_prefix = 'DATABASE_'


class TelegramBotConfig(BaseSettings):
    token: str

    class Config:
        env_prefix = 'TELEGRAM_BOT_'


class AppConfig(BaseSettings):
    _database_config_class: Type[DatabaseConfig] = DatabaseConfig
    _telegram_bot_config_class: Type[TelegramBotConfig] = TelegramBotConfig

    database: DatabaseConfig
    telegram_bot: TelegramBotConfig

    def __init__(self, *args, **kwargs):
        database = self._database_config_class(*args, **kwargs)
        telegram_bot = self._telegram_bot_config_class(*args, **kwargs)
        super().__init__(*args, **kwargs, database=database,
                         telegram_bot=telegram_bot)
