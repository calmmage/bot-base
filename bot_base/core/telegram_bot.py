import asyncio
import json
import os
import pprint
import re
import subprocess
import traceback
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from datetime import datetime
from functools import wraps
from io import BytesIO
from pathlib import Path
from tempfile import mkstemp
from textwrap import dedent
from typing import TYPE_CHECKING, Union
from typing import Type, List, Dict

import aiogram
import loguru
import pyrogram
from aiogram import F
from aiogram import types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from dotenv import load_dotenv

from bot_base.core import TelegramBotConfig
from bot_base.utils import tools_dir
from bot_base.utils.text_utils import (
    MAX_TELEGRAM_MESSAGE_LENGTH,
    split_long_message,
    escape_md,
)

if TYPE_CHECKING:
    from bot_base.core import App


# todo: find and use simple_command decorator that parses the incoming
#  message and passes the parsed data to the handler, then sends the result
#  back to the user
class TelegramBotBase(ABC):
    _config_class: Type[TelegramBotConfig] = TelegramBotConfig

    def __init__(self, config: _config_class = None, app_data="./app_data"):
        self.app_data = Path(app_data)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

        if config is None:
            config = self._load_config()
        self.config = config

        self.logger = loguru.logger.bind(component=self.__class__.__name__)
        token = config.token.get_secret_value()

        # Pyrogram
        self.pyrogram_client = self._init_pyrogram_client()

        # aiogram
        self._aiogram_bot: aiogram.Bot = aiogram.Bot(
            token=token, parse_mode=ParseMode.MARKDOWN
        )
        self._dp: aiogram.Dispatcher = aiogram.Dispatcher(bot=self._aiogram_bot)

    @property
    def downloads_dir(self):
        return self.app_data / "downloads"

    def _init_pyrogram_client(self):
        return pyrogram.Client(
            self.__class__.__name__,
            api_id=self.config.api_id.get_secret_value(),
            api_hash=self.config.api_hash.get_secret_value(),
            bot_token=self.config.token.get_secret_value(),
        )

    def _load_config(self, **kwargs):
        load_dotenv()
        return self._config_class(**kwargs)

    def register_command(self, handler, commands=None, description=None, filters=None):
        if filters is None:
            filters = ()
        if isinstance(commands, str):
            commands = [commands]
        self.logger.info(f"Registering command {commands}")
        self._commands.extend([(c.lower(), description) for c in commands])
        self._dp.message.register(handler, Command(commands=commands), *filters)

    _commands: List

    @property
    def commands(self):
        return self._commands

    NO_COMMAND_DESCRIPTION = "No description provided"

    async def _set_aiogram_bot_commands(self):
        bot_commands = [
            types.BotCommand(command=c, description=d or self.NO_COMMAND_DESCRIPTION)
            for c, d in self.commands
        ]
        await self._aiogram_bot.set_my_commands(bot_commands)

    @abstractmethod
    async def bootstrap(self):
        # todo: auto-add all commands marked with decorator
        for commands, handler_name, description, filters in command_registry:
            handler = self.__getattribute__(handler_name)
            for command in commands:
                # self._commands.append([command, description])
                # self._dp.message.register(handler, Command(commands),
                # *filters)
                pass

    async def run(self) -> None:
        await self.bootstrap()
        await self._set_aiogram_bot_commands()

        bot_name = (await self._aiogram_bot.get_me()).username
        bot_link = f"https://t.me/{bot_name}"
        self.logger.info(f"Starting telegram bot at {bot_link}")
        # And the run events dispatching
        await self._dp.start_polling(self._aiogram_bot)

    # todo: app.run(...)
    # async def download_large_file(self, chat_id, message_id):
    #     async with self.pyrogram_client as app:
    #         message = await app.get_messages(chat_id, message_ids=message_id)
    #         return await message.download(in_memory=True)

    def _check_pyrogram_tokens(self):
        if not (
            self.config.api_id.get_secret_value()
            and self.config.api_hash.get_secret_value()
        ):
            raise ValueError(
                "Telegram api_id and api_hash must be provided for Pyrogram "
                "to download large files"
            )

    async def download_large_file(self, chat_id, message_id, target_path=None):
        # todo: troubleshoot chat_id. Only username works for now.
        self._check_pyrogram_tokens()

        script_path = tools_dir / "download_file_with_pyrogram.py"

        # Construct command to run the download script
        cmd = [
            "python",
            str(script_path),
            "--chat-id",
            str(chat_id),
            "--message-id",
            str(message_id),
            "--token",
            self.config.token.get_secret_value(),
            "--api-id",
            self.config.api_id.get_secret_value(),
            "--api-hash",
            self.config.api_hash.get_secret_value(),
        ]

        if target_path:
            cmd.extend(["--target-path", target_path])
        else:
            _, file_path = mkstemp(dir=self.downloads_dir)
            cmd.extend(["--target-path", file_path])
        self.logger.debug(f"Running command: {' '.join(cmd)}")
        # Run the command in a separate thread and await its result
        result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True)
        err = result.stderr.strip().decode("utf-8")
        if "ERROR" in err:
            raise Exception(err)
        file_path = result.stdout.strip().decode("utf-8")
        self.logger.debug(f"{result.stdout=}\n\n{result.stderr=}")
        if target_path is None:
            file_data = BytesIO(open(file_path, "rb").read())
            os.unlink(file_path)
            return file_data
        return file_path


command_registry = []


Commands = Union[str, List[str]]


# todo: use decorator to mark commands and parse automatically
def mark_command(commands: Commands, description: str = None, filters: list = None):
    if isinstance(commands, str):
        commands = [commands]

    def wrapper(func):
        command_registry.append(
            dict(
                commands=commands,
                handler_name=func.__name__,
                description=description,  # todo: use docstring
                filters=filters or (),
            )
        )

        @wraps(func)
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapped

    return wrapper


class TelegramBot(TelegramBotBase):
    _commands = []

    def __init__(self, config: TelegramBotConfig = None, app: "App" = None):
        super().__init__(config)
        self.app = app

        # todo: rework to multi-chat state
        self._multi_message_mode = defaultdict(bool)
        self.messages_stack = defaultdict(list)
        self.errors = defaultdict(lambda: deque(maxlen=128))

    async def start(self, message: types.Message):
        response = dedent(
            f"""
            Hi! I'm the {self.__class__.__name__}.
            I'm based on the [bot-base](https://github.com/calmmage/bot-base) library.
            I support the following features:
            - voice messages parsing
            - hashtag and attribute recognition (#ignore, ignore=True)
            - multi-message mode
            Use /help for more details
            """
        )
        await message.answer(response)

    @mark_command(["help"], description="Show this help message")
    async def help(self, message: types.Message):
        # todo: send a description / docstring of each command
        #  I think I already implemented this somewhere.. summary bot?
        #  automatically gather docstrings of all methods with @mark_command
        # todo: bonus: use gpt for help conversation
        raise NotImplementedError

    def filter_unauthorised(self, message):
        username = message.from_user.username
        # self.logger.debug(f"checking user {username}")
        # self.logger.debug(f"Allowed users:  {self._config.allowed_users}")
        return username not in self.config.allowed_users

    UNAUTHORISED_RESPONSE = dedent("You are not authorized to use this bot.")

    async def unauthorized(self, message: types.Message):
        self.logger.info(f"Unauthorized user {message.from_user.username}")
        await message.answer(self.UNAUTHORISED_RESPONSE)

    async def chat_message_handler(self, message: types.Message):
        """
        Placeholder implementation of main chat message handler
        Parse the message as the bot will see it and send it back
        Replace with your own implementation
        """
        message_text = await self._extract_message_text(message)
        self.logger.info(
            f"Received message", user=message.from_user.username, data=message_text
        )
        if self._multi_message_mode:
            self.messages_stack.append(message)
        else:
            # todo: use "make_simpple_command_handler" to create this demo

            data = self._parse_message_text(message_text)
            response = f"Message parsed: {json.dumps(data, ensure_ascii=False)}"
            await self.send_safe(message.chat.id, response, message.message_id)

        return message_text

    async def error_handler(self, event: types.ErrorEvent, message: types.Message):
        # Get chat ID from the message. This will vary depending on the library/framework you're using.
        chat_id = message.chat.id
        error_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
            "error": str(event.exception),
            "traceback": traceback.format_exc(),
        }
        self.errors[chat_id].append(error_data)

        # Respond to the user
        await message.answer(
            "Oops, something went wrong! Use /error command if you want details"
        )

    async def error_command_handler(self, message: types.Message):
        chat_id = message.chat.id
        errors = self.errors[chat_id]
        if errors:
            error = errors[-1]
            error_message = pprint.pformat(error)
            filename = f"error_message_{error['timestamp']}.txt"
        else:
            error_message = "No recent error message captured"
            filename = ""
        await self.send_safe(
            chat_id,
            error_message,
            message.message_id,
            filename=filename,
            escape_markdown=True,
        )

    # ------------------------------------------------------------

    def _parse_message_text(self, message_text: str) -> dict:
        result = {}
        # drop the /command part if present
        if message_text.startswith("/"):
            _, message_text = message_text.split(" ", 1)

        # if it's not code - parse hashtags
        if "#code" in message_text:
            hashtags, message_text = message_text.split("#code", 1)
            # result.update(self._parse_attributes(hashtags))
            if message_text.strip():
                result["description"] = message_text
        elif "```" in message_text:
            hashtags, _ = message_text.split("```", 1)
            result.update(self._parse_attributes(hashtags))
            result["description"] = message_text
        else:
            result.update(self._parse_attributes(message_text))
            result["description"] = message_text
        return result

    hashtag_re = re.compile(r"#\w+")
    attribute_re = re.compile(r"(\w+)=(\w+)")
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
                self.logger.debug(f"Recognized hashtag: {hashtag}")
                # todo: support combining multiple queues / tags
                #  e.g. #idea #task -> queues = [ideas, tasks]
                result.update(self.recognized_hashtags[hashtag])
            else:
                self.logger.debug(f"Custom hashtag: {hashtag}")
                result[hashtag[1:]] = True

        # parse explicit keys like queue=...
        attributes = self.attribute_re.findall(text)
        for key, value in attributes:
            self.logger.debug(f"Recognized attribute: {key}={value}")
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
            # todo: accept voice message? Seems to work
            result += await self._process_voice_message(message)
        # todo: accept files?
        if message.document and message.document.mime_type == "text/plain":
            self.logger.info(f"Received text file: {message.document.file_name}")
            file = await self._aiogram_bot.download(message.document.file_id)
            content = file.read().decode("utf-8")
            result += f"\n\n{content}"
        # todo: accept video messages?
        # if message.document:

        # option 4: content - only extract if explicitly asked?
        # support multi-message content extraction?
        # todo: ... if content_parsing_mode is enabled - parse content text
        return result

    async def _process_voice_message(self, message, parallel=None):
        # extract and parse message with whisper api
        # todo: use smart filters for voice messages?
        if message.audio:
            self.logger.debug(f"Detected audio message")
            file_desc = message.audio
        elif message.voice:
            self.logger.debug(f"Detected voice message")
            file_desc = message.voice
        else:
            raise ValueError("No audio file detected")

        file = await self.download_file(message, file_desc)
        return await self.app.parse_audio(file, parallel=parallel)

    async def download_file(self, message: types.Message, file_desc, file_path=None):
        if file_desc.file_size < 20 * 1024 * 1024:
            return await self._aiogram_bot.download(
                file_desc.file_id, destination=file_path
            )
        else:
            return await self.download_large_file(
                message.chat.username, message.message_id, target_path=file_path
            )

    async def _extract_text_from_message(self, message: types.Message):
        result = await self._extract_message_text(message)

        if message.reply_to_message:
            self.logger.info(f"Detected reply message. Extracting text")
            reply_text = await self._extract_message_text(message.reply_to_message)
            self.logger.debug(f"Text extracted", data=reply_text)
            result += f"\n\n{reply_text}"

        return result

    @mark_command(commands=["multistart"], description="Start multi-message mode")
    async def multi_message_start(self, message: types.Message):
        # activate multi-message mode
        chat_id = message.chat.id
        self._multi_message_mode[chat_id] = True
        self.logger.info(
            "Multi-message mode activated", user=message.from_user.username
        )
        # todo: initiate timeout and if not deactivated - process messages
        #  automatically

    @mark_command(commands=["multiend"], description="End multi-message mode")
    async def multi_message_end(self, message: types.Message):
        # deactivate multi-message mode and process content
        chat_id = message.chat.id
        self._multi_message_mode[chat_id] = False
        self.logger.info(
            "Multi-message mode deactivated. Processing messages",
            user=message.from_user.username,
            data=str(self.messages_stack),
        )
        response = await self.process_messages_stack(chat_id)
        await message.answer(response)
        self.logger.info(
            "Messages processed", user=message.from_user.username, data=response
        )

    async def process_messages_stack(self, chat_id):
        """
        This is a placeholder implementation to demonstrate the feature
        :return:
        """
        data = await self._extract_stacked_messages_data(chat_id)
        response = f"Message parsed: {json.dumps(data)}"

        self.logger.info(f"Messages processed, clearing stack")
        self.messages_stack[chat_id] = []
        return response

    async def _extract_stacked_messages_data(self, chat_id):
        if len(self.messages_stack) == 0:
            self.logger.info("No messages to process")
            return
        self.logger.info(f"Processing {len(self.messages_stack[chat_id])} messages")
        messages_text = ""
        for message in self.messages_stack[chat_id]:
            # todo: parse message content one by one.
            #  to support parsing of the videos and other applied modifiers
            messages_text += await self._extract_message_text(message)
        return self._parse_message_text(messages_text)

    preview_cutoff = 500

    async def send_safe(
        self,
        chat_id,
        text: str,
        reply_to_message_id=None,
        filename=None,
        escape_markdown=False,
    ):
        # todo: add 3 send modes - always text, always file, auto
        if self.send_long_messages_as_files:
            if len(text) > MAX_TELEGRAM_MESSAGE_LENGTH:
                if filename is None:
                    filename = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
                preview = text[: self.preview_cutoff]
                if escape_markdown:
                    preview = escape_md(preview)
                await self._aiogram_bot.send_message(
                    chat_id,
                    dedent(
                        f"""
                        Message is too long, sending as file {escape_md(filename)} 
                        Preview: 
                        """
                    )
                    + preview
                    + "...",
                )

                await self._send_as_file(
                    chat_id,
                    text,
                    reply_to_message_id=reply_to_message_id,
                    filename=filename,
                )
            else:
                message_text = text
                if escape_markdown:
                    message_text = escape_md(text)
                if filename:
                    message_text = escape_md(filename) + message_text
                await self._aiogram_bot.send_message(
                    chat_id, message_text, reply_to_message_id=reply_to_message_id
                )
        else:
            for chunk in split_long_message(text):
                if escape_markdown:
                    chunk = escape_md(chunk)
                await self._aiogram_bot.send_message(
                    chat_id, chunk, reply_to_message_id=reply_to_message_id
                )

    async def _send_as_file(
        self, chat_id, text, reply_to_message_id=None, filename=None
    ):
        from aiogram.types.input_file import BufferedInputFile

        temp_file = BufferedInputFile(text.encode("utf-8"), filename)
        await self._aiogram_bot.send_document(
            chat_id, temp_file, reply_to_message_id=reply_to_message_id
        )

    @property
    def send_long_messages_as_files(self):
        return self.config.send_long_messages_as_files

    async def bootstrap(self):
        self._dp.error.register(self.error_handler, F.update.message.as_("message"))
        # todo: simple message parsing
        self.register_command(self.start, commands="start")
        self.register_command(self.help, commands="help")
        self.register_command(self.error_command_handler, commands="error")
        self._dp.message.register(self.unauthorized, self.filter_unauthorised)
        self.register_command(self.multi_message_start, commands="multistart")
        self.register_command(self.multi_message_end, commands="multiend")

        if self.config.test_mode:
            self.logger.debug("Running in test mode")
            self.register_command(self.test_send_file, commands="testfilesend")
            self.register_command(self.test_error_handler, commands="testerror")

        self._dp.message.register(self.chat_message_handler)

    # -----------------------------------------------------
    # TEST MODE
    # -----------------------------------------------------
    async def test_send_file(self, message: types.Message):
        self.logger.debug("Received testfilesend command")
        await self._send_as_file(message.chat.id, "test text", message.message_id)

    async def test_error_handler(self, message: types.Message):
        self.logger.debug("Received testerror command")
        raise Exception("TestError")
