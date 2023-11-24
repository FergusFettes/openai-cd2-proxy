import uuid
import os
import csv
import time
import asyncio
import aiohttp
import random

from models import APIKey, db

messages = [uuid.uuid4().hex for _ in range(100)]

# Configuration parameters
ENDPOINT_URL = "http://localhost:5000/v1/completions"  # Replace with your actual endpoint
REQUEST_INTERVAL_SEC = 3
TEST_API_KEY_PREFIX = "test_api_key_"  # Prefix for the API keys
IDENTITY_COUNT = 30

# Shutdown event signal
shutdown_event = asyncio.Event()

LOG_FILE = "api_benchmark_log.csv"


def log_to_csv(timestamp, identity, duration, status_code):
    with open(LOG_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, identity, duration, status_code])


async def make_request(identity, session):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TEST_API_KEY_PREFIX}{identity}"
    }
    try:
        start_time = time.time()  # Start timing here
        REQUEST_PAYLOAD = {"prompt": random.choice(messages)}
        async with session.post(ENDPOINT_URL, json=REQUEST_PAYLOAD, headers=headers) as response:
            duration = time.time() - start_time  # Calculate the duration
            if response.status == 200:
                result = await response.json()
                if result["choices"][0]["text"] != REQUEST_PAYLOAD["prompt"]:
                    print(f"Identity {identity} received invalid response: {result}")
                    response.status = 500
                else:
                    print(f"{duration:.2f}s - Identity {identity} received valid response: {result}")
            else:
                print(f"{duration:.2f}s - Identity {identity} received error response: {response.status}")
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_to_csv(timestamp, identity, duration, response.status)
    except aiohttp.ClientError as e:
        duration = time.time() - start_time  # Calculate the duration, even on error
        print(f"{duration:.2f}s - Request failed for identity {identity}: {e}")
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_to_csv(timestamp, identity, duration, response.status)


async def identity_worker(identity):
    await asyncio.sleep(random.randint(REQUEST_INTERVAL_SEC - 2, REQUEST_INTERVAL_SEC + 2))
    print(f"Identity {identity} has been started up.")
    async with aiohttp.ClientSession() as session:
        while not shutdown_event.is_set():
            await make_request(identity, session)
            await asyncio.sleep(random.randint(REQUEST_INTERVAL_SEC - 2, REQUEST_INTERVAL_SEC + 2))
        print(f"Identity {identity} has been shut down.")


async def main():
    tasks = [asyncio.create_task(identity_worker(identity)) for identity in range(IDENTITY_COUNT)]

    try:
        # Wait until shutdown_event is set
        await shutdown_event.wait()
    finally:
        # Gather all tasks to perform cleanup
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def initialize_api_keys():
    for identity in range(IDENTITY_COUNT):
        name = f"test_{identity}"
        api_key = f"{TEST_API_KEY_PREFIX}{identity}"
        APIKey.get_or_create(name=name, defaults={'api_key': api_key})
        print(f"Created API key for identity {identity}")
    db.commit()


if __name__ == "__main__":
    # Initialize CSV file with headers
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Identity", "Duration", "StatusCode"])

    initialize_api_keys()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutdown signal received. Shutting down.")
        shutdown_event.set()
