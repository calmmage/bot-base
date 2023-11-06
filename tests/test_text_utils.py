import pytest

from bot_base.utils.text_utils import escape_md


@pytest.mark.parametrize(
    "text, escaped_text",
    [
        (
            "This is a test [string] with *some* special characters!",
            "This is a test \\[string\\] with \\*some\\* special characters\\!",
        ),
    ],
)
def test_escape_md(text, escaped_text):
    assert escape_md(text) == escaped_text
