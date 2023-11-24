import asyncio
from typing import Optional, Union, List
import time
from sys import argv

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

from openai_proxy.models import APIKey, Usage, init_db, cli
from openai_proxy.request_handler import RequestHandler
from openai_proxy.utils import logger


app = FastAPI()
request_handler = RequestHandler()


@app.on_event("startup")
async def startup():
    await init_db()
    request_handler.process_task = asyncio.create_task(request_handler.process_requests_periodically())


@app.on_event("shutdown")
async def shutdown():
    request_handler.process_task.cancel()
    await request_handler.process_task


class CompletionRequest(BaseModel):
    prompt: Union[List[str], str]
    max_tokens: Optional[int] = None
    n: Optional[int] = None
    stop: Optional[List[str]] = None
    temperature: Optional[float] = None


@app.post("/v1/completions")
async def handle_request(completion_request: CompletionRequest, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid API key")

    api_key = authorization[7:]
    key_info = await APIKey.filter(api_key=api_key).first()

    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid API key")

    await Usage.create(name=key_info.name, time=time.time())

    logger.debug(f"Adding request: {completion_request.prompt}")
    event, value = await request_handler.add_request(completion_request.dict())
    response, status_code = await request_handler.package_response(event, value)
    logger.debug(f"Response: {response}")
    return response


if __name__ == "__main__":
    if len(argv) == 1:
        import uvicorn
        uvicorn.run(app, port=5000)
    else:
        cli()
