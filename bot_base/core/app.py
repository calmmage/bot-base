import asyncio
from io import BytesIO
from typing import Type

import loguru
import mongoengine
import openai
from dotenv import load_dotenv
from pydub import AudioSegment

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
        try:
            return mongoengine.get_connection('default')
        except mongoengine.connection.ConnectionFailure:
            db_config = self.config.database
            return mongoengine.connect(db=db_config.name,
                                       # alias = db_config.name
                                       host=db_config.conn_str)

    def run(self):
        self.logger.info(f"Starting {self.__class__.__name__}")
        asyncio.run(self.bot.run())


class App(AppBase):
    def __init__(self, config: AppConfig = None):
        super().__init__(config=config)
        self._init_openai()

    def _init_openai(self):
        openai.api_key = self.config.openai_api_key

    async def parse_audio(self, audio_path: str, period: int = 120 * 1000,
                          buffer: int = 10 * 1000, parallel: bool = True):
        audio = AudioSegment.from_file(audio_path)
        # todo: async requests to openai
        # todo: return results as they come

        chunks = []
        s = 0
        while s + period < len(audio):
            # todo: add buffer
            chunks.append(audio[s: s + period])
            s += period - buffer
        chunks.append(audio[s:])
        self.logger.info(f"Split into {len(chunks)} chunks")

        # # Now you can save these chunks to files:
        for i, chunk in enumerate(chunks):
            with open(f"chunk_{i}.mp3", "wb") as f:
                chunk.export(f, format="mp3")

        in_memory_audio_files = {}

        for i, chunk in enumerate(chunks):
            buffer = BytesIO()
            chunk.export(buffer, format="mp3")
            buffer.name = f"chunk_{i}.mp3"
            in_memory_audio_files[i] = buffer

        # joined_text = ""
        results = {}

        async def parse_chunk(i, audio):
            # audio.name = f"chunk_{i}.mp3"
            # results[i] = await openai.Audio.atranscribe_raw("whisper-1",
            # audio, filename=f"chunk_{i}.mp3")
            results[i] = await openai.Audio.atranscribe("whisper-1", audio)

        if parallel:
            await asyncio.gather(*[parse_chunk(i, chunk) for i, chunk in
                                   in_memory_audio_files.items()])
        else:
            for i, chunk in in_memory_audio_files.items():
                await parse_chunk(i, chunk)

        transcript = "\n\n".join([results[i].text for i in range(len(chunks))])
        self.logger.info(f"Parsed audio: {transcript}")
        return transcript
