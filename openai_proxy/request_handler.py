from os import getenv
import json
import time
from threading import Event, Thread
import queue

from openai import OpenAI

from openai_proxy.utils import logger

from dotenv import load_dotenv
load_dotenv()


client = OpenAI(
    api_key=getenv("OCP_OPENAI_API_KEY"),
    organization=getenv("OCP_OPENAI_ORG"),
    base_url=getenv("OCP_OPENAI_API_BASE")
)


class RequestHandler:
    # Wait for 3 seconds so there are no more than 20 requests per minute
    SERVER_WAIT_TIME = 3

    def __init__(self, data_path="data.json", model="code-davinci-002"):
        self.data_path = data_path
        self.model = model
        self.requests_queue = queue.Queue()

        # Check if 'localhost' in the API base URL, if so set the wait time to 0
        if "localhost" in client.base_url:
            self.SERVER_WAIT_TIME = 0

    def add_request(self, params):
        shared_params = {k: v for k, v in params.items() if k != "prompt" and v is not None}
        shared_params["model"] = self.model

        batch_id = self._generate_batch_id(shared_params)

        event = Event()
        value = {"prompt": params["prompt"], "event": event, "response": None}

        self.requests_queue.put((batch_id, shared_params, value))
        logger.debug(f"{self.requests_queue.qsize()} requests in queue")

        return event, value

    def _generate_batch_id(self, shared_params):
        # This can be any function that uniquely identifies a set of parameters.
        # For simplicity, we're using the JSON representation of the sorted items of the dictionary.
        return json.dumps(tuple(sorted(shared_params.items())), sort_keys=True)

    def package_response(self, event, value):
        # Wait for the event to be set by the request processing thread.
        event.wait()
        # Once the event is set, the response is ready in the value object.
        return value["response"], 200

    def request_openai_api(self, shared_params, prompts):
        return client.Completion.create(
            prompt=prompts,
            **shared_params
        )

    def process_request_batch(self, batch_id, shared_params, prompts, values):
        # Request OpenAI API for the batch
        logger.debug(f"Requesting OpenAI API with batch of size {len(prompts)}")
        response = self.request_openai_api(shared_params, prompts)

        n = shared_params.get("n", 1)
        choices = response["choices"]
        grouped_choices = [choices[i:i + n] for i in range(0, len(choices), n)]

        for value, group in zip(values, grouped_choices):
            value["response"] = {"choices": group}
            value["event"].set()

    def _process_requests(self):
        while True:
            time.sleep(0.1)
            # Initialize a dictionary to batch requests with the same parameters
            batched_requests = {}
            while not self.requests_queue.empty():
                # While there are items in the queue, aggregate them by batch_id
                batch_id, shared_params, value = self.requests_queue.get_nowait()
                if batch_id not in batched_requests:
                    batched_requests[batch_id] = {
                        "shared_params": shared_params,
                        "prompts": [],
                        "values": []
                    }
                batched_requests[batch_id]["prompts"].append(value["prompt"])
                batched_requests[batch_id]["values"].append(value)
                self.requests_queue.task_done()

            # Now process each batch of requests
            for batch_id, batch_data in batched_requests.items():
                self.process_request_batch(
                    batch_id,
                    batch_data["shared_params"],
                    batch_data["prompts"],
                    batch_data["values"]
                )

            time.sleep(self.SERVER_WAIT_TIME)

    def run(self):
        logger.debug("Starting request processing thread")
        self.request_thread = Thread(target=self._process_requests, daemon=True)
        self.request_thread.start()
        logger.debug("Request processing thread started")

    def stop(self):
        logger.debug("Stopping request processing thread")
        # Clear the queue
        while not self.requests_queue.empty():
            self.requests_queue.get_nowait()
            self.requests_queue.task_done()
        self.request_thread.join()
        logger.debug("Request processing thread stopped")

