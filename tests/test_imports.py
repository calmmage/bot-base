import pytest


# todo: test mongo connection with pytest-mongodb

# def test_imports():
#     from bot_base.core import (AppConfig, TelegramBotConfig, DatabaseConfig,
#                                App, TelegramBot)
#     from bot_base.core.app import AppBase
#     from bot_base.core.telegram_bot import BotBase


@pytest.fixture(scope="function")
def setup_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_CONN_STR", "")
    monkeypatch.setenv("DATABASE_NAME", "test_db")
    monkeypatch.setenv(
        "TELEGRAM_BOT_TOKEN", "1234567890:aaabbbcccdd-aaabbbcccdddeee_abcdefg"
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-1234567890")


def test_init(setup_environment):
    from bot_base.core import App, AppConfig

    app = App()
    assert isinstance(app.config, AppConfig)
