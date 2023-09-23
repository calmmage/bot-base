import pytest

from bot_base.utils.logging_utils import format_logging_message, DATA_CUTOFF


@pytest.mark.parametrize(
    "message, expected",
    [
        (
            {
                "level": {"name": "INFO"},
                "message": "Test Message",
                "extra": {"data": "This is some data to log"},
            },
            "INFO: Test Message - data (Total length: 24): This is some data to log",
        ),
        (
            {"level": {"name": "WARNING"}, "message": "Test Message", "extra": {}},
            "WARNING: Test Message",
        ),
        (
            {
                "level": {"name": "INFO"},
                "message": "Test Message",
                "extra": {"data": "A" * 2 * DATA_CUTOFF},
            },
            "INFO: Test Message - data (Total length: 200): "
            + "A" * DATA_CUTOFF
            + "...",
        ),
    ],
)
def test_custom_sink(message, expected):
    result = format_logging_message(message)
    assert expected == result


if __name__ == "__main__":
    pytest.main()
