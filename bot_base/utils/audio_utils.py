from io import BytesIO

import asyncio
import loguru
import pydub
from pydub import AudioSegment
from tqdm.auto import tqdm

from bot_base.utils.gpt_utils import Audio, atranscribe_audio, transcribe_audio

DEFAULT_PERIOD = 120 * 1000
DEFAULT_BUFFER = 5 * 1000


def split_audio(
    audio: pydub.AudioSegment, period=DEFAULT_PERIOD, buffer=DEFAULT_BUFFER, logger=None
):
    if logger is None:
        logger = loguru.logger
    chunks = []
    s = 0
    while s + period < len(audio):
        chunks.append(audio[s : s + period])
        s += period - buffer
    chunks.append(audio[s:])
    logger.info(f"Split into {len(chunks)} chunks")

    in_memory_audio_files = []

    logger.debug(f"Converting chunks to mp3")
    for i, chunk in enumerate(chunks):
        buffer = BytesIO()
        chunk.export(buffer, format="mp3")  # check which format it is and
        # use the same
        buffer.name = f"chunk_{i}.mp3"
        in_memory_audio_files.append(buffer)

    return in_memory_audio_files


async def split_and_transcribe_audio(
    audio: Audio,
    period: int = DEFAULT_PERIOD,
    buffer: int = DEFAULT_BUFFER,
    parallel: bool = None,
    logger=None,
):
    if logger is None:
        logger = loguru.logger

    if isinstance(audio, str):
        audio = AudioSegment.from_file(audio)
    if not isinstance(audio, AudioSegment):
        audio = AudioSegment.from_file(audio)

    audio_chunks = split_audio(audio, period=period, buffer=buffer, logger=logger)

    # joined_text = ""
    results = {}

    # todo: rework with gather
    # async def parse_chunk(i, audio):
    #     logger.debug(f"Starting to parse chunk {i}")
    #     results[i] = await atranscribe_audio(audio)
    #     logger.debug(f"Finished parsing chunk {i}")

    if parallel:
        logger.info("Processing chunks in parallel")
        tasks = map(atranscribe_audio, audio_chunks)
        text_chunks = await asyncio.gather(*tasks)
    else:
        logger.info("Processing chunks sequentially")
        text_chunks = map(transcribe_audio, tqdm(audio_chunks))

    chunks = [results[i].text for i in range(len(chunks))]
    logger.info(f"Parsed audio: {chunks}")
    return chunks
