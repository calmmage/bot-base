import re

MAX_TELEGRAM_MESSAGE_LENGTH = 4096


def split_long_message(text, max_length=MAX_TELEGRAM_MESSAGE_LENGTH, sep="\n"):
    chunks = []
    while len(text) > max_length:
        chunk = text[:max_length]
        if sep:
            # split the text on the last sep character, if it exists
            last_sep = chunk.rfind(sep)
            if last_sep != -1:
                chunk = chunk[: last_sep + 1]
        text = text[len(chunk) :]
        chunks.append(chunk)
    if text:
        chunks.append(text)  # add the remaining text as the last chunk
    return chunks


SPECIAL_CHARS = r"\\_\*\[\]\(\)~`><&#+\-=\|\{\}\.\!"


escape_re = re.compile(f"[{SPECIAL_CHARS}]")


def escape_md(text: str) -> str:
    """Escape markdown special characters in the text."""
    return escape_re.sub(r"\\\g<0>", text)


DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 50


def split_text_with_overlap(
    text, chunk_size=DEFAULT_CHUNK_SIZE, chunk_overlap=DEFAULT_CHUNK_OVERLAP
):
    """
    Splits a given text into smaller chunks using the RecursiveCharacterTextSplitter.

    This function is particularly useful for splitting large texts into smaller
    parts that are easier to manage and process, especially when dealing with
    language models that have token limits.

    Args:
        text (str): The text to be split into smaller chunks.
        chunk_size (int, optional): The size of each chunk in characters. Default is 1000.
        chunk_overlap (int, optional): The number of characters to overlap between chunks.
                                       Default is 50.

    Returns:
        list: A list of text chunks created from the original text.

    Example:
        >>> text = "This is a sample text that is longer than the chunk size."
        >>> split_text_with_overlap(text, chunk_size=10, chunk_overlap=5)
        ['This is a ', 'is a sample', 'ample text ', 'text that i', 'hat is long', 'is longer ', 'nger than ', 'han the chu', 'e chunk siz', 'chunk size.']
    """
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    return text_splitter.split_text(text)
