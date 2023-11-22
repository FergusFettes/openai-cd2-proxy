import time
import asyncio
import aiohttp
import random

# Configuration parameters
ENDPOINT_URL = "http://localhost:5000/v1/completions"  # Replace with your actual endpoint
REQUEST_INTERVAL_SEC = 5
TEST_API_KEY_PREFIX = "test_api_key_"  # Prefix for the API keys
IDENTITY_COUNT = 30
REQUEST_PAYLOAD = {
    "prompt": "Hello World",
    "max_tokens": 60
}

# Shutdown event signal
shutdown_event = asyncio.Event()


async def make_request(identity, session):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TEST_API_KEY_PREFIX}{identity}"
    }
    try:
        print(f"Identity {identity} attempting request")
        start_time = time.time()  # Start timing here
        async with session.post(ENDPOINT_URL, json=REQUEST_PAYLOAD, headers=headers) as response:
            duration = time.time() - start_time  # Calculate the duration
            if response.status == 200:
                result = await response.json()
                print(f"{duration:.2f}s - Identity {identity} received valid response: {result}")
            else:
                print(f"{duration:.2f}s - Identity {identity} received error response: {response.status}")
    except aiohttp.ClientError as e:
        duration = time.time() - start_time  # Calculate the duration, even on error
        print(f"{duration:.2f}s - Request failed for identity {identity}: {e}")


async def identity_worker(identity):
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

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutdown signal received. Shutting down.")
        shutdown_event.set()
