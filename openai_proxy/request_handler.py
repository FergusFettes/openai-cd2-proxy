from os import getenv
import json
import asyncio
from asyncio import Queue, Event
from typing import Any, Dict

from openai import AsyncClient

from openai_proxy.utils import logger

from dotenv import load_dotenv
load_dotenv()


client = AsyncClient(
    api_key=getenv("OCP_OPENAI_API_KEY"),
    organization=getenv("OCP_OPENAI_ORG"),
    base_url=getenv("OCP_OPENAI_API_BASE")
)


class RequestHandler:
    SERVER_WAIT_TIME = 3  # Wait for 3 seconds to manage request frequency

    def __init__(self, data_path="data.json", model="code-davinci-002"):
        self.data_path = data_path
        self.model = model
        self.requests_queue = Queue()

        # Check if 'localhost' in the API base URL, if so set the wait time to 0
        if "localhost" in str(client.base_url):
            self.SERVER_WAIT_TIME = 0

    async def add_request(self, params: Dict[str, Any]) -> Any:
        shared_params = {k: v for k, v in params.items() if k != "prompt" and v is not None}
        shared_params["model"] = self.model

        batch_id = self._generate_batch_id(shared_params)

        event = Event()
        value = {"prompt": params["prompt"], "event": event, "response": None}

        await self.requests_queue.put((batch_id, shared_params, value))
        logger.debug(f"{self.requests_queue.qsize()} requests in queue")

        return event, value

    def _generate_batch_id(self, shared_params: Dict[str, Any]) -> str:
        return json.dumps(tuple(sorted(shared_params.items())), sort_keys=True)

    async def package_response(self, event: Event, value: Any) -> Any:
        await event.wait()
        return value["response"], 200

    async def request_openai_api(self, shared_params: Dict[str, Any], prompts: Any) -> Any:
        return await client.completions.create(
            prompt=prompts,
            **shared_params
        )

    async def process_request_batch(self, batch_id: str, shared_params: Dict[str, Any], prompts: Any, values: Any):
        logger.debug(f"Requesting OpenAI API with batch of size {len(prompts)}")
        response = await self.request_openai_api(shared_params, prompts)

        n = shared_params.get("n", 1)
        choices = response.choices
        grouped_choices = [choices[i:i + n] for i in range(0, len(choices), n)]

        for value, group in zip(values, grouped_choices):
            value["response"] = {"choices": group}
            value["event"].set()

    async def process_requests_periodically(self):
        try:
            while True:
                # The coroutine will pause here until at least one item is available.
                batch_id, shared_params, value = await self.requests_queue.get()
                batched_requests = {
                    batch_id: {
                        "shared_params": shared_params,
                        "prompts": [value["prompt"]],
                        "values": [value]
                    }
                }

                while not self.requests_queue.empty():
                    batch_id, shared_params, value = await self.requests_queue.get()
                    if batch_id in batched_requests:
                        batched_requests[batch_id]["prompts"].append(value["prompt"])
                        batched_requests[batch_id]["values"].append(value)
                    else:
                        batched_requests[batch_id] = {
                            "shared_params": shared_params,
                            "prompts": [value["prompt"]],
                            "values": [value]
                        }
                    self.requests_queue.task_done()

                # Process each batch
                for batch_id, batch_data in batched_requests.items():
                    await self.process_request_batch(
                        batch_id,
                        batch_data["shared_params"],
                        batch_data["prompts"],
                        batch_data["values"]
                    )

                # Delay before the next iteration of the loop.
                await asyncio.sleep(self.SERVER_WAIT_TIME)

        except asyncio.CancelledError:
            logger.debug("Request processing has been cancelled")
