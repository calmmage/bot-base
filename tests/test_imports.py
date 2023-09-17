# todo: test mongo connection with pytest-mongodb

# def test_imports():
#     from bot_base.core import (AppConfig, TelegramBotConfig, DatabaseConfig,
#                                App, TelegramBot)
#     from bot_base.core.app import AppBase
#     from bot_base.core.telegram_bot import BotBase

def test_init():
    from bot_base.core import App, AppConfig
    app = App()
    assert isinstance(app.config, AppConfig)
