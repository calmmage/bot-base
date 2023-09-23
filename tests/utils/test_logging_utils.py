import pytest

from bot_base.utils.logging_utils import setup_logger


def test_setup_logger():
    setup_logger(log_to_stderr=True, log_to_file=True)


if __name__ == "__main__":
    pytest.main()
