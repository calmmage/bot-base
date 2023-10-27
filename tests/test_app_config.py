import pytest

from bot_base.core.app_config import AppConfig


@pytest.fixture
def app_config():
    return AppConfig()


def test_data_dir_default(app_config):
    assert str(app_config.data_dir) == "app_data"


def test_database_config_default(app_config):
    assert app_config.database.conn_str.get_secret_value() == ""
    assert app_config.database.name == ""


def test_telegram_bot_config_default(app_config):
    assert app_config.telegram_bot.token.get_secret_value() == ""
    assert app_config.telegram_bot.api_id.get_secret_value() == ""
    assert app_config.telegram_bot.api_hash.get_secret_value() == ""
    assert app_config.telegram_bot.send_long_messages_as_files is True
    assert app_config.telegram_bot.test_mode is False
    assert app_config.telegram_bot.allowed_users == []
    assert app_config.telegram_bot.dev_message_timeout == 5 * 60
    assert app_config.telegram_bot.parse_mode is None
    assert app_config.telegram_bot.send_preview_for_long_messages is False


def test_enable_openai_api_default(app_config):
    assert app_config.enable_openai_api is False
    assert app_config.openai_api_key.get_secret_value() == ""


def test_enable_voice_recognition_default(app_config):
    assert app_config.enable_voice_recognition is False
    assert app_config.process_audio_in_parallel is False


def test_enable_scheduler_default(app_config):
    assert app_config.enbale_scheduler is False
