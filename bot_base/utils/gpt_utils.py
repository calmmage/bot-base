import asyncio
import json
from functools import partial
from typing import Union

import openai
import pydub
import tiktoken

token_limit_by_model = {
    "gpt-3.5-turbo": 8192,
    "gpt-4": 4096,
    "gpt-3.5-turbo-16k": 16384,
}


def get_token_count(text, model="gpt-3.5-turbo"):
    """
    calculate amount of tokens in text
    model: gpt-3.5-turbo, gpt-4
    """
    # To get the tokeniser corresponding to a specific model in the OpenAI API:
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))


def run_command_with_gpt(command: str, data: str, model="gpt-3.5-turbo"):
    messages = [{"role": "user", "content": command}, {"role": "user", "content": data}]
    response = openai.ChatCompletion.create(messages=messages, model=model)
    return response.choices[0].text


async def arun_command_with_gpt(command: str, data: str, model="gpt-3.5-turbo"):
    messages = [{"role": "user", "content": command}, {"role": "user", "content": data}]
    response = await openai.ChatCompletion.acreate(messages=messages, model=model)
    return response.choices[0].text


Audio = Union[pydub.AudioSegment, str]


def transcribe_audio(audio: Audio, model="whisper-1"):
    if isinstance(audio, str):
        audio = openai.Audio.from_file(audio)
    return openai.Audio.atranscribe(model, audio)


async def atranscribe_audio(audio: Audio, model="whisper-1"):
    if isinstance(audio, str):
        audio = openai.Audio.from_file(audio)
    return await openai.Audio.atranscribe(model, audio)


def apply_command_recursively(command, chunks, model="gpt-3.5-turbo"):
    """
    Apply GPT command recursively to the data
    """

    # token_limit = token_limit_by_model[model]
    while len(chunks) > 1:
        # step 1: get token counts
        token_counts = [get_token_count(chunk, model=model) for chunk in chunks]
        # step 2: group chunks in groups up to the model token limit
    raise NotImplementedError


def map_gpt_command(chunks, command, all_results=False):
    """
    Run GPT command on each chunk one by one
    Accumulating temporary results and supplying them to the next chunk
    """
    temporary_results = None
    results = []
    for chunk in chunks:
        data = {"TEXT": chunk, "TEMPORARY_RESULTS": temporary_results}
        data_str = json.dumps(data, ensure_ascii=False)
        temporary_results = run_command_with_gpt(command, data_str)
        results.append(temporary_results)

    if all_results:
        return results
    else:
        return results[-1]


MERGE_COMMAND_TEMPLATE = """
You're merge assistant. The following command was applied to each chunk.
The results are separated by keyword "{keyword}"
You have to merge all the results into one. 
COMMAND:
{command}
"""


async def amap_gpt_command(chunks, command, model="gpt-3.5-turbo", merge=False):
    """
    Run GPT command on each chunk in parallel
    Merge results if merge=True
    """
    tasks = map(partial(arun_command_with_gpt, command=command, model=model), chunks)

    # Using asyncio.gather to collect all results
    completed_tasks = await asyncio.gather(*tasks)

    if merge:
        merge_command = MERGE_COMMAND_TEMPLATE.format(
            command=command, keyword="TEMPORARY_RESULT:"
        ).strip()
        return apply_command_recursively(merge_command, completed_tasks, model=model)
    else:
        return completed_tasks
