import json
import os
import re
import tempfile
from abc import ABC, abstractmethod
from datetime import datetime
from functools import wraps
from textwrap import dedent
from typing import TYPE_CHECKING
from typing import Type, List, Dict

import aiogram
import loguru
from aiogram import types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import FSInputFile
from dotenv import load_dotenv

from bot_base.core import TelegramBotConfig
from bot_base.utils.telegram_utils import split_long_message, \
    MAX_TELEGRAM_MESSAGE_LENGTH

if TYPE_CHECKING:
    from bot_base.core import App


# todo: find and use simple_command decorator that parses the incoming
#  message and passes the parsed data to the handler, then sends the result
#  back to the user
class TelegramBotBase(ABC):
    _config_class: Type[TelegramBotConfig] = TelegramBotConfig

    def __init__(self, config: _config_class = None):
        if config is None:
            config = self._load_config()
        self._config = config

        self.logger = loguru.logger.bind(component=self.__class__.__name__)

        self._aiogram_bot: aiogram.Bot = aiogram.Bot(
            token=config.token,
            parse_mode=ParseMode.MARKDOWN
        )

        # # All handlers should be attached to the Router (or Dispatcher)
        self._dp: aiogram.Dispatcher = aiogram.Dispatcher(bot=self._aiogram_bot)

    def _load_config(self, **kwargs):
        load_dotenv()
        return self._config_class(**kwargs)

    def register_command(self, handler, commands=None, description=None):
        if commands is None:
            # register a simple message handler
            command_decorator = self._dp.message()
        else:
            self._commands.extend([(c, description) for c in commands])
            command_decorator = self._dp.message(Command(commands=commands))
        self.logger.info(f"Registering command {commands}")
        command_decorator(handler)

    _commands: List

    @property
    def commands(self):
        return self._commands

    NO_COMMAND_DESCRIPTION = "No description provided"

    async def _set_bot_commands(self):
        bot_commands = [
            types.BotCommand(command=c,
                             description=d or self.NO_COMMAND_DESCRIPTION)
            for c, d in self.commands
        ]
        await self._aiogram_bot.set_my_commands(bot_commands)

    @abstractmethod
    async def bootstrap(self):
        pass
        # super().bootstrap()

    async def run(self) -> None:
        await self.bootstrap()
        await self._set_bot_commands()

        bot_name = (await self._aiogram_bot.get_me()).username
        bot_link = f"https://t.me/{bot_name}"
        self.logger.info(f"Starting telegram bot at {bot_link}")
        # And the run events dispatching
        await self._dp.start_polling(self._aiogram_bot)


# todo: use decorator to mark commands and parse automatically
def mark_command(commands: List[str] = None, description: str = None):
    def wrapper(func):
        func._command_description = dict(
            commands=commands,
            description=description
        )

        @wraps(func)
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapped

    return wrapper


class TelegramBot(TelegramBotBase):
    _commands = []

    def __init__(self, config: TelegramBotConfig = None,
                 app: 'App' = None):
        super().__init__(config)
        self.app = app

        self._multi_message_mode = False
        self.messages_stack = []

    async def start(self, message: types.Message):
        response = dedent(f"""
            Hi! I'm the {self.__class__.__name__}.
            I'm based on the [bot-base](https://github.com/calmmage/bot-base) library.
            I support the following features:
            - voice messages parsing
            - hashtag and attribute recognition (#ignore, ignore=True)
            - multi-message mode
            Use /help for more details
            """)
        await message.answer(response)

    @mark_command(['help'], description="Show this help message")
    async def help(self, message: types.Message):
        # todo: send a description / docstring of each command
        #  I think I already implemented this somewhere.. summary bot?
        #  automatically gather docstrings of all methods with @mark_command
        # todo: bonus: use gpt for help conversation
        raise NotImplementedError

    async def chat_message_handler(self, message: types.Message):
        """
        Placeholder implementation of main chat message handler
        Parse the message as the bot will see it and send it back
        Replace with your own implementation
        """
        message_text = await self._extract_message_text(message)
        self.logger.info(f"Received message: {message_text}")
        if self._multi_message_mode:
            self.messages_stack.append(message)
        else:
            # todo: use "make_simpple_command_handler" to create this demo

            data = self._parse_message_text(message_text)
            response = f"Message parsed: {json.dumps(data, ensure_ascii=False)}"
            # await message.answer(response)
            await self.send_safe(message.chat.id, response, message.message_id)

        return message_text

    def _parse_message_text(self, message_text: str) -> dict:
        result = {}
        # drop the /command part if present
        if message_text.startswith('/'):
            _, message_text = message_text.split(' ', 1)

        # if it's not code - parse hashtags
        if '#code' in message_text:
            hashtags, message_text = message_text.split('#code', 1)
            # result.update(self._parse_attributes(hashtags))
            if message_text.strip():
                result['description'] = message_text
        elif '```' in message_text:
            hashtags, _ = message_text.split('```', 1)
            result.update(self._parse_attributes(hashtags))
            result['description'] = message_text
        else:
            result.update(self._parse_attributes(message_text))
            result['description'] = message_text
        return result

    hashtag_re = re.compile(r'#\w+')
    attribute_re = re.compile(r'(\w+)=(\w+)')
    # todo: make abstract
    # todo: add docstring / help string/ a way to view this list of
    #  recognized tags. Log when a tag is recognized
    # recognized_hashtags = {  # todo: add tags or type to preserve info
    #     '#idea': {'queue': 'ideas'},
    #     '#task': {'queue': 'tasks'},
    #     '#shopping': {'queue': 'shopping'},
    #     '#recommendation': {'queue': 'recommendations'},
    #     '#feed': {'queue': 'feed'},
    #     '#content': {'queue': 'content'},
    #     '#feedback': {'queue': 'feedback'}
    # }
    # todo: how do I add a docstring / example of the proper format?
    recognized_hashtags: Dict[str, Dict[str, str]] = {}

    def _parse_attributes(self, text):
        result = {}
        # use regex to extract hashtags
        # parse hashtags
        hashtags = self.hashtag_re.findall(text)
        # if hashtag is recognized - parse it
        for hashtag in hashtags:
            if hashtag in self.recognized_hashtags:
                self.logger.info(f"Recognized hashtag: {hashtag}")
                # todo: support combining multiple queues / tags
                #  e.g. #idea #task -> queues = [ideas, tasks]
                result.update(self.recognized_hashtags[hashtag])
            else:
                self.logger.info(f"Custom hashtag: {hashtag}")
                result[hashtag[1:]] = True

        # parse explicit keys like queue=...
        attributes = self.attribute_re.findall(text)
        for key, value in attributes:
            self.logger.info(f"Recognized attribute: {key}={value}")
            result[key] = value

        return result

    async def _extract_message_text(self, message: types.Message) -> str:
        result = ""
        # option 1: message text
        if message.text:
            result += message.md_text
        # option 2: caption
        if message.caption:
            result += message.caption
        # option 3: voice/video message
        if message.voice or message.audio:
            # todo: accept voice message
            # result += await self._process_voice_message(message.voice)
            result += await self._process_voice_message(message)
        # option 4: content - only extract if explicitly asked?
        # support multi-message content extraction?
        # todo: ... if content_parsing_mode is enabled - parse content text
        return result

    async def _process_voice_message(self, message):  # todo
        # extract and parse message with whisper api
        # todo: use app, not whisper directly
        # todo: use smart filters for voice messages?
        if message.audio:
            audio_file_id = message.audio.file_id
        else:
            audio_file_id = message.voice.file_id

        # download the file
        await message.answer(f"Downloading audio file from {audio_file_id}")
        # audio_file = await message.bot.download_file_by_id(audio_url)
        # self._aiogram_bot.download(audio_file, "temp.mp3")

        audio_file = await self._aiogram_bot.get_file(audio_file_id)

        # Create a temporary directory to store the file
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file_path = os.path.join(temp_dir, "temp_audio_file")

            await self._aiogram_bot.download(audio_file,
                                             destination=temp_file_path)

            return await self.app.parse_audio(temp_file_path)

    @mark_command(commands=['multistart'],
                  description="Start multi-message mode")
    async def multi_message_start(self, message: types.Message):
        # activate multi-message mode
        self._multi_message_mode = True
        self.logger.info("Multi-message mode activated")
        # todo: initiate timeout and if not deactivated - process messages
        #  automatically

    @mark_command(commands=['multiend'], description="End multi-message mode")
    async def multi_message_end(self, message: types.Message):
        # deactivate multi-message mode and process content
        self._multi_message_mode = False
        self.logger.info("Multi-message mode deactivated. Processing messages")
        response = await self.process_messages_stack()
        await message.answer(response)
        self.logger.info("Messages processed")  # todo: report results / link

    async def process_messages_stack(self):
        """
        This is a placeholder implementation to demonstrate the feature
        :return:
        """
        data = await self._extract_stacked_messages_data()
        response = f"Message parsed: {json.dumps(data)}"

        self.logger.info(f"Messages processed, clearing stack")
        self.messages_stack = []
        return response

    async def _extract_stacked_messages_data(self):
        if len(self.messages_stack) == 0:
            self.logger.info("No messages to process")
            return
        self.logger.info(f"Processing {len(self.messages_stack)} messages")
        messages_text = ""
        for message in self.messages_stack:
            # todo: parse message content one by one.
            #  to support parsing of the videos and other applied modifiers
            messages_text += await self._extract_message_text(message)
        return self._parse_message_text(messages_text)

    async def send_safe(self, chat_id, text: str, reply_to_message_id=None):
        # todo: consider alternative: send as text file attachment
        # option 1: make a setting
        # option 2: if > 4096 - send as file
        # option 3: send as file + send start of text at the same time
        if self.send_long_messages_as_files:
            if len(text) > MAX_TELEGRAM_MESSAGE_LENGTH:
                await self._aiogram_bot.send_message(
                    chat_id, split_long_message(text)[0])
                date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                filename = f"transcript_{date}.txt"
                await self._send_as_file(
                    chat_id, text, reply_to_message_id=reply_to_message_id,
                    filename=filename
                )
            else:
                await self._aiogram_bot.send_message(
                    chat_id, text, reply_to_message_id=reply_to_message_id)
        else:
            for chunk in split_long_message(text):
                await self._aiogram_bot.send_message(
                    chat_id, chunk, reply_to_message_id=reply_to_message_id)

    async def _send_as_file(self, chat_id, text, reply_to_message_id=None,
                            filename=None):

        # Create a temporary dir
        with tempfile.TemporaryDirectory() as temp_dir:
            date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            if filename is None:
                filename = f"{date}.txt"
            temp_file_path = os.path.join(temp_dir, filename)

            # Write the text data to the temporary file
            with open(temp_file_path, 'w') as temp_file:
                temp_file.write(text)
            self.logger.debug(f"Sending file saved at {temp_file_path}")
            # Send the file using Aiogram
            await self._aiogram_bot.send_document(
                chat_id, FSInputFile(temp_file_path),
                reply_to_message_id=reply_to_message_id)

    @property
    def send_long_messages_as_files(self):
        return self._config.send_long_messages_as_files

    async def bootstrap(self):
        # todo: simple message parsing
        self.register_command(self.start, commands=['start'])
        self.register_command(self.help, commands=['help'])
        self.register_command(self.multi_message_start, commands=['multistart'])
        self.register_command(self.multi_message_end, commands=['multiend'])

        if self._config.test_mode:
            self.logger.debug("Running in test mode")
            self.register_command(self.test_send_file,
                                  commands=['testfilesend'])

        self.register_command(self.chat_message_handler)

    # -----------------------------------------------------
    # TEST MODE
    # -----------------------------------------------------
    async def test_send_file(self, message: types.Message):
        self.logger.debug("Received testfilesend command")
        await self._send_as_file(message.chat.id, "test text",
                                 message.message_id)
