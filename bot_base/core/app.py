import asyncio
from typing import Type

import loguru
import mongoengine
import openai
from dotenv import load_dotenv

from bot_base.core import DatabaseConfig, TelegramBotConfig
from bot_base.core.app_config import AppConfig
from bot_base.core.telegram_bot import TelegramBot
from bot_base.utils.audio_utils import (
    DEFAULT_PERIOD,
    DEFAULT_BUFFER,
    split_and_transcribe_audio,
)
from bot_base.utils.gpt_utils import Audio


class AppBase:
    _app_config_class: Type[AppConfig] = AppConfig
    _telegram_bot_class: Type[TelegramBot] = TelegramBot
    _database_config_class: Type[DatabaseConfig] = DatabaseConfig
    _telegram_bot_config_class: Type[TelegramBotConfig] = TelegramBotConfig

    def __init__(self, config: _app_config_class = None):
        self.logger = loguru.logger.bind(component=self.__class__.__name__)
        if config is None:
            config = self._load_config()
        self.config = config
        self.db = self._connect_db()
        self.bot = self._telegram_bot_class(config.telegram_bot, app=self)
        self.logger.info(f"Loaded config: {self.config}")

    def _load_config(self, **kwargs):
        load_dotenv()
        database_config = self._database_config_class(**kwargs)
        telegram_bot_config = self._telegram_bot_config_class(**kwargs)
        return self._app_config_class(
            database=database_config, telegram_bot=telegram_bot_config, **kwargs
        )

    def _connect_db(self):
        try:
            return mongoengine.get_connection("default")
        except mongoengine.connection.ConnectionFailure:
            db_config = self.config.database
            conn_str = db_config.conn_str.get_secret_value()
            return mongoengine.connect(
                db=db_config.name,
                host=conn_str,
            )

    def run(self):
        self.logger.info(f"Starting {self.__class__.__name__}")
        asyncio.run(self.bot.run())


class App(AppBase):
    def __init__(self, config: AppConfig = None):
        super().__init__(config=config)
        self._init_openai()

    def _init_openai(self):
        openai.api_key = self.config.openai_api_key.get_secret_value()

    async def parse_audio(
        self,
        audio: Audio,
        period: int = DEFAULT_PERIOD,
        buffer: int = DEFAULT_BUFFER,
        parallel: bool = None,
    ):
        if parallel is None:
            parallel = self.config.process_audio_in_parallel
        chunks = await split_and_transcribe_audio(
            audio,
            period=period,
            buffer=buffer,
            parallel=parallel,
            logger=self.logger,
        )
        return chunks
