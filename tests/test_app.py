import pytest

from bot_base.core import TelegramBot
from bot_base.core.app import App, AppBase


#
@pytest.fixture(scope="function")
def setup_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_CONN_STR", "")
    monkeypatch.setenv("DATABASE_NAME", "test_db")
    monkeypatch.setenv(
        "TELEGRAM_BOT_TOKEN", "1234567890:aaabbbcccdd-aaabbbcccdddeee_abcdefg"
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-1234567890")


@pytest.fixture
def app(setup_environment):
    from bot_base.core.app_config import AppConfig

    config = AppConfig()
    return App(config=config)


@pytest.fixture
def app_base(setup_environment):
    from bot_base.core.app_config import AppConfig

    config = AppConfig()
    return AppBase(config=config)


def test_app_data_dir(app):
    assert str(app.data_dir) == "app_data"
    # check that the dir exists
    assert app.data_dir.exists()


def test_app_config(app):
    from bot_base.core.app_config import AppConfig

    assert isinstance(app.config, AppConfig)


def test_app_db_connection(app):
    assert app.db is not None


def test_app_telegram_bot(app):
    assert isinstance(app.bot, TelegramBot)


def test_app_logger(app):
    assert app.logger is not None


# def test_app_run(app):
#     app.run()


def test_app_base_data_dir(app_base):
    assert str(app_base.data_dir) == "app_data"
    # check that the dir exists
    assert app_base.data_dir.exists()


def test_app_base_config(app_base):
    from bot_base.core.app_config import AppConfig

    assert isinstance(app_base.config, AppConfig)


def test_app_base_db_connection(app_base):
    assert app_base.db is not None


def test_app_base_telegram_bot(app_base):
    assert isinstance(app_base.bot, TelegramBot)


def test_app_base_logger(app_base):
    assert app_base.logger is not None


# def test_app_base_run(app_base):
#     app_base.run()
