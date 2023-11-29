import os
import uuid
import asyncio
import csv
import json
import time
import random

import aiohttp


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
