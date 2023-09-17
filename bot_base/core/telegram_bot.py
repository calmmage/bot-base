import json
import re
from abc import ABC, abstractmethod
from textwrap import dedent
from typing import TYPE_CHECKING
from typing import Type, List, Dict

import aiogram
import loguru
from aiogram import types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from dotenv import load_dotenv

from app_config import TelegramBotConfig

if TYPE_CHECKING:
    from app import App


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
        self.bootstrap()

    def _load_config(self, **kwargs):
        load_dotenv()
        return self._config_class(**kwargs)

    @abstractmethod
    def bootstrap(self):
        pass

    def register_command(self, handler, commands=None):
        if commands is None:
            # register a simple message handler
            command_decorator = self._dp.message()
        else:
            command_decorator = self._dp.message(Command(commands=commands))
        command_decorator(handler)

    async def run(self) -> None:
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

        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapped

    return wrapper


class TelegramBot(TelegramBotBase):
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

    @mark_command()
    async def chat_message_handler(self, message: types.Message):
        """
        Placeholder implementation of main chat message handler
        Parse the message as the bot will see it and send it back
        Replace with your own implementation
        """
        message_text = self._extract_message_text(message)
        self.logger.info(f"Received message: {message_text}")
        if self._multi_message_mode:
            self.messages_stack.append(message)
        else:
            # todo: use "make_simpple_command_handler" to create this demo

            data = self._parse_message_text(message_text)
            response = f"Message parsed: {json.dumps(data)}"
            await message.answer(response)

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

    def _extract_message_text(self, message: types.Message) -> str:
        result = ""
        # option 1: message text
        if message.text:
            result += message.md_text
        # option 2: caption
        if message.caption:
            result += message.caption
        # option 3: voice/video message
        if message.voice:
            result += self._process_voice_message(message.voice)
        # option 4: content - only extract if explicitly asked?
        # support multi-message content extraction?
        # todo: ... if content_parsing_mode is enabled - parse content text
        return result

    def _process_voice_message(self, voice_message):
        # extract and parse message with whisper api
        # todo: use app, not whisper directly
        # todo: use smart filters for voice messages?
        raise NotImplementedError

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
        if len(self.messages_stack) == 0:
            self.logger.info("No messages to process")
            return
        self.logger.info(f"Processing {len(self.messages_stack)} messages")
        messages_text = ""
        for message in self.messages_stack:
            # todo: parse message content one by one.
            #  to support parsing of the videos and other applied modifiers
            messages_text += self._extract_message_text(message)
        data = self._parse_message_text(messages_text)
        response = f"Message parsed: {json.dumps(data)}"

        return response

    def bootstrap(self):
        # todo: simple message parsing
        self.register_command(self.chat_message_handler)
        self.register_command(self.start, commands=['start'])
        self.register_command(self.help, commands=['help'])
        self.register_command(self.multi_message_start, commands=['multistart'])
        self.register_command(self.multi_message_end, commands=['multiend'])
