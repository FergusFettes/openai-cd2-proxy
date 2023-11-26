import json
import uuid
import csv
import time
import asyncio
import aiohttp
import random
from pathlib import Path

from tortoise import Tortoise

from openai_proxy import APIKey, init_db

messages = [uuid.uuid4().hex for _ in range(100)]

# Configuration parameters
ENDPOINT_URL = "http://localhost:5000/v1/completions"  # Replace with your actual endpoint
TEST_API_KEY_PREFIX = "test_api_key_"  # Prefix for the API keys

# Shutdown event signal
shutdown_event = asyncio.Event()


def log_to_csv(logfile, timestamp, identity, duration, status_code):
    with open(logfile, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, identity, duration, status_code])


async def make_request(logfile, identity, session, parameters):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TEST_API_KEY_PREFIX}{identity}"
    }
    try:
        start_time = time.time()  # Start timing here
        REQUEST_PAYLOAD = {
            "prompt": random.choice(messages),
            "max_tokens": random.randint(10, 10 + parameters - 1)
        }
        async with session.post(ENDPOINT_URL, json=REQUEST_PAYLOAD, headers=headers) as response:
            duration = time.time() - start_time  # Calculate the duration
            if response.status == 200:
                result = await response.json()
                text = result["choices"][0]["text"].split("||")[0]
                params = json.loads(result["choices"][0]["text"].split("||")[1])
                if text != REQUEST_PAYLOAD["prompt"] or params["max_tokens"] != REQUEST_PAYLOAD["max_tokens"]:
                    print(f"Identity {identity} received invalid response: {text}{params}")
                    response.status = 500
                else:
                    print(f"{duration:.2f}s - Identity {identity} received valid response: {text}{params}")
            else:
                print(f"{duration:.2f}s - Identity {identity} received error response: {response.status}")
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_to_csv(logfile, timestamp, identity, duration, response.status)
    except aiohttp.ClientError as e:
        duration = time.time() - start_time  # Calculate the duration, even on error
        print(f"{duration:.2f}s - Request failed for identity {identity}: {e}")
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_to_csv(timestamp, identity, duration, response.status)


async def identity_worker(logfile, identity, request_pause, parameters):
    await asyncio.sleep(random.randint(request_pause - 2, request_pause + 2))
    print(f"Identity {identity} has been started up.")
    async with aiohttp.ClientSession() as session:
        while not shutdown_event.is_set():
            await make_request(logfile, identity, session, parameters)
            await asyncio.sleep(random.randint(request_pause - 2, request_pause + 2))
        print(f"Identity {identity} has been shut down.")


async def initialize_api_keys(identities):
    await init_db()
    for identity in range(identities):
        name = f"test_{identity}"
        api_key = f"{TEST_API_KEY_PREFIX}{identity}"
        await APIKey.get_or_create(name=name, defaults={'api_key': api_key})
        print(f"Created API key for identity {identity}")
    await Tortoise.close_connections()


async def main(logfile, identities, request_pause, parameters):
    # Initialize API keys
    await initialize_api_keys(identities)

    tasks = [
        asyncio.create_task(
            identity_worker(logfile, identity, request_pause, parameters)
        ) for identity in range(identities)
    ]

    try:
        # Wait until shutdown_event is set
        await shutdown_event.wait()
    finally:
        # Gather all tasks to perform cleanup
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


import typer

cli = typer.Typer()


@cli.command()
def cli_main(log: bool = True, identities: int = 300, request_pause: int = 3, parameters: int = 1):
    # Initialize CSV file with headers
    if log:
        logfile = f"{identities}_ids_{request_pause}_pause_{parameters}_params.csv"
    if not Path(logfile).exists():
        with open(logfile, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Identity", "Duration", "StatusCode"])

    try:
        asyncio.run(main(logfile, identities, request_pause, parameters))
    except KeyboardInterrupt:
        print("Shutdown signal received. Shutting down.")
        shutdown_event.set()


if __name__ == "__main__":
    cli()
