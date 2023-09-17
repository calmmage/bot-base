import re
from abc import ABC, abstractmethod
from typing import Type, List

import aiogram
import loguru
from aiogram import types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from dotenv import load_dotenv

from app_config import TelegramBotConfig


class BotBase(ABC):
    _config_class: Type[TelegramBotConfig] = TelegramBotConfig

    logger = loguru.logger.bind(component="TelegramBot")

    def __init__(self, config: _config_class = None):
        if config is None:
            config = self._load_config()
        self._config = config
        # Initialize Bot instance with a default parse mode
        # which will be passed to all API calls
        self._aiogram_bot = aiogram.Bot(token=config.token,
                                        parse_mode=ParseMode.MARKDOWN)

        # # All handlers should be attached to the Router (or Dispatcher)
        # dp = Dispatcher()
        self._dp = aiogram.Dispatcher(bot=self._aiogram_bot)
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


class TelegramBot(BotBase):
    def __init__(self, config: TelegramBotConfig = None, app: 'App' = None):
        super().__init__(config)
        self.app = app

        self._multi_message_mode = False
        self.messages_stack = []

    def parse_message(self, message: types.Message) -> SQDQueueItemMessage:
        # todo: extract media - photos, videos - content as well and save to
        #  Notion
        data = self._process_message_text(message)

        return SQDQueueItemMessage(
            **data
        )

    def _process_message_text(self, message: types.Message, message_text: str
    = None) -> Dict[str, str]:
        if message_text is None:
            message_text = self._extract_message_text(message)
        data = self._parse_message_text(message_text)

        if 'description' not in data:
            data['description'] = message_text
        if 'name' not in data:
            data['name'] = self._generate_name(message_text)
        if 'queue' not in data:
            data['queue'] = self._determine_queue(message)
        if 'url' not in data:
            data['url'] = self._extract_url(message_text)
        return data

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
    recognized_hashtags = {  # todo: add tags or type to preserve info
        '#idea': {'queue': 'ideas'},
        '#task': {'queue': 'tasks'},
        '#shopping': {'queue': 'shopping'},
        '#recommendation': {'queue': 'recommendations'},
        '#feed': {'queue': 'feed'},
        '#content': {'queue': 'content'},
        '#feedback': {'queue': 'feedback'}
    }

    def _parse_attributes(self, text):
        result = {}
        # use regex to extract hashtags
        # parse hashtags
        hashtags = self.hashtag_re.findall(text)
        # if hashtag is recognized - parse it
        for hashtag in hashtags:
            if hashtag in self.recognized_hashtags:
                # todo: support multiple queues / tags
                result.update(self.recognized_hashtags[hashtag])
            else:
                result[hashtag[1:]] = True

        # parse explicit keys like queue=...
        attributes = self.attribute_re.findall(text)
        for key, value in attributes:
            result[key] = value

        return result

    @staticmethod
    def _generate_name(message_text: str) -> str:
        # topic + date
        # todo: generate name with gpt (3?)
        topic = message_text.strip().split('\n')[0].replace(' ', '-').lower()

        date = datetime.now().strftime("%Y-%m-%d")
        return f"{topic}-{date}"

    @staticmethod
    def _determine_queue(message: types.Message) -> str:
        # for now - default
        # todo: use chat_id -> queue mapping
        return 'default'
        # todo: determine queue based on message content
        # option 1: use gpt (send message text and list of queues with
        # descriptions)
        # option 2: use gpt with function-calling (allow gpt to peek into ?

    url_re = re.compile(r'https?://(?:[-\w.]|%[\da-fA-F]{2})+')

    def _extract_url(self, message_text, message: types.Message = None):
        # option 1: if message contains url - extract it.
        # Support hidden links
        # message_text = message.md_text
        # todo: add support for multi-url case
        data = self.url_re.findall(message_text)
        if data:
            return data[0]

        # option 2: Save to Notion and then store Notion page url
        pass

        # option 3: If there's media content - save and add a link to it
        pass
        return None

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

        self.process_messages_stack()
        self.logger.info("Messages processed")  # todo: report results / link

    def process_messages_stack(self):
        if len(self.messages_stack) == 0:
            self.logger.info("No messages to process")
            return
        self.logger.info(f"Processing {len(self.messages_stack)} messages")
        messages_text = ""
        for message in self.messages_stack:
            # todo: parse message content one by one.
            #  to support parsing of the videos and other applied modifiers
            messages_text += self._extract_message_text(message)

        data = self._process_message_text(self.messages_stack[0], messages_text)

        item = SQDQueueItemMessage(
            **data
        )
        self.app.add_item(item)

        self.logger.info(f"Messages processed, clearing stack")
        self.messages_stack = []
        # return item

    async def process_message(self, message: types.Message):
        if self._multi_message_mode:
            self.messages_stack.append(message)
        else:
            # todo: make some smarter logic here. for example - pick between
            # add item and bulk add
            # automatically start multi-message mode
            await self.add_item(message)

    def bootstrap(self):
        # todo: simple message parsing
        self.register_command(self.process_message)
        # self.register_command(self.on_setup, commands=['setup'])
        self.register_command(self.add_item, commands=['add'])
        self.register_command(self.multi_message_start, commands=['multistart'])
        self.register_command(self.multi_message_end, commands=['multiend'])
        # todo: /setup command
        # todo: /bulkadd command

    # ------------------------------------------------------
    # New Commands
    # ------------------------------------------------------

    @mark_command(commands=['addqueue'], description="Add a new queue")
    def add_queue(self, message: types.Message):
        raise NotImplementedError

    @mark_command(commands=['register'], description="Setup a new queue")
    async def register_queue(self, message: types.Message):
        """
        # register a new chat config
        # components:
        #  1) queue = . default = defaut
        #  2) chat_id = defualt = this chat
        #  3) type = default = output
        # idea:
        #  possible chat connection type
        #  1) Input
        #  2) Output
        #  3) Archive
        """
        message_text = self._extract_message_text(message)
        data = self._parse_message_text(message_text)
        if 'queue' not in data:
            data['queue'] = 'default'
        if 'chat_id' not in data:
            data['chat_id'] = message.chat.id
        if 'type' not in data:
            data['type'] = 'output'

        item = SQDQueueInfoMessage(**data)
        self.app.add_queue(item)

    @mark_command(commands=['bulkadd'],
                  description="Add multiple items to queue")
    async def bulk_add(self, message: types.Message):
        # Idea: split a single message into multiple items and process them
        #  one by one. Use gpt to split the message into multiple items?
        # Simple MVP: split by newlines, -
        # bonus: sub-items with indentationbul

        # todo: hard - support multi-message mode

        # todo: bonus - add an option to #guess automatically

        # todo: request missing data one by one
        raise NotImplementedError

    @mark_command()
    async def get(self, message: types.Message):
        """
        Get item using provided info appropriately
        - If there's key - get by key
        - if #random - get random item
        - if nothing - get latest
        """
        pass

    @mark_command()
    async def get_item(self, message: types.Message):
        """
        # get item by id / key
        """
        pass

# def run_bot():
#     bot = TelegramBot()
#     # todo: use loguru
#     logging.basicConfig(level=logging.INFO, stream=sys.stdout)
#     asyncio.run(bot.run())
