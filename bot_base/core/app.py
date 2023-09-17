import asyncio
from typing import Type

import loguru
import mongoengine
from dotenv import load_dotenv

from bot_base.core.app_config import AppConfig
from bot_base.core.telegram_bot import TelegramBot


class AppBase:
    _app_config_class: Type[AppConfig] = AppConfig
    _telegram_bot_class: Type[TelegramBot] = TelegramBot

    def __init__(self, config: _app_config_class = None):
        self.logger = loguru.logger.bind(component=self.__class__.__name__)
        if config is None:
            config = self._load_config()
        self.config = config
        self.db = self._connect_db()
        self.bot = self._telegram_bot_class(config.telegram_bot, app=self)

    def _load_config(self, **kwargs):
        load_dotenv()
        return self._app_config_class(**kwargs)

    def _connect_db(self):
        db_config = self.config.database
        return mongoengine.connect(db=db_config.name,  # alias = db_config.name
                                   host=db_config.conn_str)

    def run(self):
        self.logger.info(f"Starting {self.__class__.__name__}")
        asyncio.run(self.bot.run())
