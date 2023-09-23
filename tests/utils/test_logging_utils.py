import pytest
from easydict import EasyDict

from bot_base.utils.logging_utils import (
    format_logging_message,
    DATA_CUTOFF,
    setup_logger,
)


@pytest.mark.parametrize(
    "message, expected",
    [
        (
            EasyDict(
                {
                    "level": {"name": "INFO"},
                    "message": "Test Message",
                    "extra": {"data": "This is some data to log"},
                }
            ),
            "INFO: Test Message - data (Total length: 24): This is some data to log",
        ),
        (
            EasyDict(
                {"level": {"name": "WARNING"}, "message": "Test Message", "extra": {}}
            ),
            "WARNING: Test Message",
        ),
        (
            EasyDict(
                {
                    "level": {"name": "INFO"},
                    "message": "Test Message",
                    "extra": {"data": "A" * 2 * DATA_CUTOFF},
                }
            ),
            "INFO: Test Message - data (Total length: 200): "
            + "A" * DATA_CUTOFF
            + "...",
        ),
    ],
)
def test_custom_sink(message, expected):
    result = format_logging_message(message)
    assert expected == result


def test_setup_logger():
    setup_logger(log_to_stderr=True, log_to_file=True)


if __name__ == "__main__":
    pytest.main()
