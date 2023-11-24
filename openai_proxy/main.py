import time
from sys import argv

from fastapi import FastAPI, HTTPException, Header
from models import APIKey, Usage, init_db, cli

from openai_proxy.request_handler import RequestHandler
from openai_proxy.utils import logger


app = FastAPI()
request_handler = RequestHandler()


async def startup():
    await init_db()

app.add_event_handler("startup", startup)


@app.post("/v1/completions")
async def handle_request(prompt: str, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid API key")

    api_key = authorization[7:]
    key_info = await APIKey.filter(api_key=api_key).first()

    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid API key")

    await Usage.create(name=key_info.name, time=time.time())

    logger.debug(f"Adding request: {prompt}")
    event, value = await request_handler.add_request({"prompt": prompt})
    response, status_code = request_handler.package_response(event, value)
    logger.debug(f"Response: {response}")
    return response


def run_server():
    request_handler.run()
    app.run()


if __name__ == "__main__":
    if len(argv) == 1:
        run_server()
    else:
        cli()
