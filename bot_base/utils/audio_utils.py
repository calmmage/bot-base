import asyncio
import gc
import loguru
import pprint
import tempfile
import tqdm
from io import BytesIO
from pydub import AudioSegment
from typing import BinaryIO

from bot_base.utils.gpt_utils import (
    Audio,
    atranscribe_audio,
    transcribe_audio,
    WHISPER_RATE_LIMIT,
)

DEFAULT_PERIOD = 120 * 1000
DEFAULT_BUFFER = 5 * 1000


def make_audio_buffer(audio: AudioSegment, name=None, in_memory: bool = True) -> str:
    """
    Depending on the in_memory flag, either:
    Exports the audio segment to a buffer and returns it, or
    Writes the audio segment to a temporary file on disk and returns the file path.
    The 'name' parameter is used as a filename prefix.
    """
    if in_memory:
        buffer = BytesIO()
        audio.export(buffer, format="mp3")
        buffer.seek(0)  # Rewind the buffer to the beginning
        buffer.name = f"{name}.mp3" if name else "audio.mp3"
        return buffer
    else:
        prefix = f"{name}_" if name else "audio_"
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, prefix=prefix, suffix=".mp3"
        )
        audio.export(temp_file.name, format="mp3")
        temp_file.close()
        return temp_file.name


async def split_and_transcribe_audio(
    audio: Audio,
    period: int = DEFAULT_PERIOD,
    buffer: int = DEFAULT_BUFFER,
    parallel: bool = None,
    parallel_size_limit: int = 60 * 60 * 1000,  # 1 hour
    in_memory=True,
    logger=None,
):
    if logger is None:
        logger = loguru.logger

    if isinstance(audio, (str, BytesIO, BinaryIO)):
        logger.debug(f"Loading audio from {audio}")
        audio = AudioSegment.from_file(audio)

    if len(audio) > parallel_size_limit:
        logger.warning(
            f"Audio is too long ({len(audio)} ms), disabling parallel processing"
        )
        parallel = False
        in_memory = False

    audio_chunks = split_audio(
        audio, period=period, buffer=buffer, logger=logger, in_memory=in_memory
    )
    del audio  # Remove reference to the original audio object
    gc.collect()  # Suggest garbage collection

    if parallel:
        logger.info("Processing chunks in parallel")
        tasks = map(atranscribe_audio, audio_chunks)
        text_chunks = await asyncio.gather(*tasks)
    else:
        logger.info("Processing chunks sequentially")
        text_chunks = []
        for chunk in tqdm.std.tqdm(audio_chunks):
            text_chunks.append(transcribe_audio(chunk))
            # todo: free memory after each chunk

    logger.debug(f"Parsed audio", data=pprint.pformat(text_chunks))
    return text_chunks


def split_audio(
    audio: Audio,
    period=DEFAULT_PERIOD,
    buffer=DEFAULT_BUFFER,
    logger=None,
    in_memory=True,
):
    if isinstance(audio, (str, BytesIO, BinaryIO)):
        logger.debug(f"Loading audio from {audio}")
        audio_file = audio
        audio = AudioSegment.from_file(audio_file)
        AudioSegment.from_file_using_temporary_files()
        try:
            audio_file.close()
        except:
            pass
        del audio_file
        gc.collect()
    if logger is None:
        logger = loguru.logger
    chunks = []
    # optimize chunk count for the whisper rate limit
    # todo: implement global rate limiter instead
    if len(audio) / period > WHISPER_RATE_LIMIT - 5:
        period = len(audio) // (WHISPER_RATE_LIMIT - 5)

    logger.debug(f"Splitting audio into chunks")
    i = 0
    while period < len(audio):
        # use the same
        yield make_audio_buffer(audio[:period], f"chunk_{i}.mp3", in_memory=in_memory)
        audio = audio[period - buffer :]
        gc.collect()
        i += 1

    yield make_audio_buffer(audio, f"chunk_{i}.mp3", in_memory=in_memory)

    logger.debug(f"Split into {len(chunks)} chunks")
