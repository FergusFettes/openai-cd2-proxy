import asyncio
from typing import Optional, Union, List
import time
from sys import argv
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from fastapi_utils.timing import add_timing_middleware

from openai_proxy import APIKey, Usage, Performance, init_db, cli
from openai_proxy.request_handler import RequestHandler
from openai_proxy.utils import logger
import tiktoken


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting lifespan")
    await init_db()
    request_handler.process_task = asyncio.create_task(request_handler.process_requests_periodically())

    logger.info("Starting app")
    yield

    logger.info("Stopping app")
    request_handler.process_task.cancel()
    await request_handler.process_task


app = FastAPI(lifespan=lifespan)
add_timing_middleware(app, record=logger.info, prefix="app", exclude="untimed")
request_handler = RequestHandler()
enc = tiktoken.encoding_for_model("code-davinci-002")


class CompletionRequest(BaseModel):
    prompt: Union[List[str], str]
    max_tokens: Optional[int] = None
    n: Optional[int] = None
    stop: Optional[List[str]] = None
    temperature: Optional[float] = None


@app.post("/v1/completions")
async def completion(completion_request: CompletionRequest, authorization: str = Header(None)):
    start = time.time()             # TODO: see if i can get durations from the timing middleware?
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid API key")

    api_key = authorization[7:]
    key_info = await APIKey.filter(api_key=api_key).first()

    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid API key")

    input_tokens = len(enc.encode(completion_request.prompt))
    await Usage.create(
        name=key_info.name,
        time=time.time(),
        tokens=input_tokens,
        type="prompt",
    )

    logger.debug(f"Adding request: {completion_request.prompt}")
    event, value = await request_handler.add_request(completion_request.dict())

    # Wait for the response to be ready
    await event.wait()
    response = value["response"]

    logger.debug(f"Response: {response}")

    await Usage.create(
        name=key_info.name,
        time=time.time(),
        tokens=get_response_length(response),
        type="completion",
    )

    await Performance.create(
        time=time.time(),
        duration=time.time() - start,
        success=True
    )

    return response


def get_response_length(response):
    total = 0
    for choice in response['choices']:
        total += len(enc.encode(choice.text))
    return total


@app.get("/v1/usage")
async def usage(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid API key")

    api_key = authorization[7:]
    key_info = await APIKey.filter(api_key=api_key).first()

    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid API key")

    usages = await Usage.filter(name=key_info.name).all()
    total = 0
    for usage in usages:
        total += usage.tokens
    return total


@app.get("/v1/leaderboard")
async def leaderboard(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid API key")

    api_key = authorization[7:]
    key_info = await APIKey.filter(api_key=api_key).first()

    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid API key")

    users = await APIKey.filter(leaderboard=True).all()
    leaderboard = {}
    for user in users:
        usages = await Usage.filter(name=user.name).all()
        leaderboard[user.name] = 0
        for usage in usages:
            leaderboard[user.name] += usage.tokens

    return leaderboard


@app.get("/v1/leaderboard_toggle")
async def leaderboard_toggle(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid API key")

    api_key = authorization[7:]
    key_info = await APIKey.filter(api_key=api_key).first()

    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid API key")

    key_info.leaderboard = not key_info.leaderboard
    await key_info.save()

    return f"You are now {'not ' if not key_info.leaderboard else ''}on the leaderboard."


if __name__ == "__main__":
    if len(argv) == 1:
        import uvicorn
        uvicorn.run(app, port=5000)
    else:
        cli()
