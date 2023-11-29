import signal
import os
import uuid
import asyncio
import csv
import json
import time
import random

import aiohttp
from tortoise import Tortoise

from openai_proxy import APIKey, init_db


async def initialize_api_keys(identities, prefix):
    await init_db()
    for identity in range(identities):
        name = f"test_{identity}"
        api_key = f"{prefix}{identity}"
        await APIKey.get_or_create(name=name, defaults={'api_key': api_key})
        print(f"Created API key for identity {identity}")
    await Tortoise.close_connections()


async def log_to_csv(logfile, identity, timestamp, duration, status_code):
    # Check if the logfile exists and if not, create it with headers
    file_exists = os.path.isfile(logfile)
    with open(logfile, mode='a', newline='') as file:
        writer = csv.writer(file)
        # If the file didn't exist before this process, write the header
        if not file_exists:
            writer.writerow(['timestamp', 'identity', 'duration', 'status_code'])
            print(f"Created new logfile: {logfile}")
        writer.writerow([timestamp, identity, duration, status_code])


def response_validation(status, response_json, payload, start_time, identity):
    if status == 200:
        # Do the validity check here with "response" and "payload" as needed
        text = response_json["choices"][0]["text"].split("||")[0]
        params = json.loads(response_json["choices"][0]["text"].split("||")[1])
        # Example response validity check
        if text != payload["prompt"] or params["max_tokens"] != payload["max_tokens"]:
            print(
                f"{time.time() - start_time:.2f}s - "
                f"Identity {identity} received invalid response: {text}{params}"
            )
            status = 500
        else:
            print(
                f"{time.time() - start_time:.2f}s - "
                f"Identity {identity} received valid response: {text}{params}"
            )
    else:
        print(
            f"{time.time() - start_time:.2f}s - "
            f"Identity {identity} received error response: {status}"
        )
        status = 500
    return status


class Requester:
    def __init__(self, identity, request_pause, parameters, endpoint_url, logfile, test_api_key_prefix):
        self.identity = identity
        self.request_pause = request_pause
        self.parameters = parameters
        self.endpoint_url = endpoint_url
        self.logfile = logfile
        self.test_api_key_prefix = test_api_key_prefix
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.test_api_key_prefix}{self.identity}"
        }
        self.shutdown_event = asyncio.Event()

    async def make_request(self, session):
        request_payload = {
            "prompt": uuid.uuid4().hex,
            "max_tokens": random.randint(10, 10 + self.parameters - 1)
        }

        start_time = time.time()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            async with session.post(
                self.endpoint_url, json=request_payload, headers=self.headers
            ) as response:
                status = response_validation(
                    response.status,
                    await response.json(),
                    request_payload,
                    start_time,
                    self.identity
                )

        except aiohttp.ClientError as e:
            print(
                f"{time.time() - start_time:.2f}s - "
                f"Request failed for identity {self.identity}: {e}"
            )
            status = 500

        # Calculate duration in all cases
        duration = time.time() - start_time
        await log_to_csv(self.logfile, self.identity, timestamp, duration, status)

    async def wait_random_time(self):
        await asyncio.sleep(random.uniform(
            self.request_pause - 2,
            self.request_pause + 2
        ))

    async def run(self):
        await self.wait_random_time()
        print(f"Identity {self.identity} has been started up.")
        async with aiohttp.ClientSession() as session:
            while not self.shutdown_event.is_set():
                await self.make_request(session)
                await self.wait_random_time()
        print(f"Identity {self.identity} has been shut down.")


class Benchmark:
    def __init__(self, identities):
        self.identities = identities
        self.shutdown_event = asyncio.Event()

    def handle_shutdown_signal(self, signum, frame):
        print(f"Received shutdown signal ({signal.strsignal(signum)}). Shutting down.")
        for requester in self.requesters:
            requester.shutdown_event.set()

    def create_tasks(self):
        # Register system signals for graceful termination (optional based on your environment)
        signal.signal(signal.SIGINT, self.handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self.handle_shutdown_signal)

        tasks = []
        for i, requester in enumerate(self.requesters):
            task = asyncio.create_task(self.staggered_start(requester, i))
            tasks.append(task)

        print(f"Starting benchmark with {len(self.requesters)} identities...")
        return tasks

    async def staggered_start(self, requester, index):
        # Wait a bit before starting each requester based on their index
        initial_wait = random.uniform(0, self.request_pause) * index
        await asyncio.sleep(initial_wait)
        await requester.run()

    async def shutdown_task(self, seconds):
        await asyncio.sleep(seconds)
        for requester in self.requesters:
            requester.shutdown_event.set()

    async def run(self):
        tasks = self.create_tasks()
        shutdown_task = asyncio.create_task(self.shutdown_task(60))
        tasks = [*tasks, shutdown_task]

        await asyncio.gather(*tasks)

    def stop(self):
        for requester in self.requesters:
            requester.shutdown_event.set()


import typer


app = typer.Typer()


@app.command()
def main(
    identities: int = typer.Option(10, help="Number of identities."),
    request_pause: float = typer.Option(5.0, help="Time to pause between requests."),
    parameter_sets: int = typer.Option(3, help="Number of parameter sets."),
    endpoint_url: str = typer.Option(
        "http://localhost:5000/v1/completions",
        help="URL of the proxy server endpoint."
    ),
    logfile: str = typer.Option("requests_log.csv", help="Path to the CSV logfile."),
    test_api_key_prefix: str = typer.Option("test_api_key_", help="Test API key prefix.")
):
    # Initialize API keys
    asyncio.run(initialize_api_keys(identities, test_api_key_prefix))

    # Create a list of requesters
    requesters = [
        Requester(
            identity=i,
            request_pause=request_pause,
            parameters=parameter_sets,
            endpoint_url=endpoint_url,
            logfile=logfile,
            test_api_key_prefix=test_api_key_prefix
        ) for i in range(identities)
    ]

    # Create a benchmark runner
    benchmark = Benchmark(identities)
    benchmark.requesters = requesters
    benchmark.request_pause = request_pause

    # Run the Benchmark
    try:
        asyncio.run(benchmark.run())
    except KeyboardInterrupt:
        print("Shutdown signal received. Shutting down.")
        benchmark.stop()


if __name__ == "__main__":
    app()
