from os import getenv
import json
import time
from threading import Event, Lock, Thread
import openai
import queue

from dotenv import load_dotenv
load_dotenv()

openai.api_key = getenv("OCP_OPENAI_API_KEY")
openai.organization = getenv("OCP_OPENAI_ORG")
openai.api_base = getenv("OCP_OPENAI_API_BASE")


class RequestHandler:
    def __init__(self, data_path="data.json", model="code-davinci-002"):
        self.lock = Lock()
        self.data_path = data_path
        self.model = model
        self.requests_queue = queue.Queue()
        self.load_data()

    def load_data(self):
        try:
            with open(self.data_path) as f:
                self.data = json.load(f)
        except FileNotFoundError:
            self.data = {"api_keys": [], "usage": []}

    def save_data(self):
        with open(self.data_path, "w") as f:
            json.dump(self.data, f)

    def validate_api_key(self, api_key_full):
        if not api_key_full.startswith("Bearer "):
            return False, "Invalid API key"
        api_key = api_key_full[7:]
        self.load_data()
        matching_keys = [key for key in self.data["api_keys"] if key["api_key"] == api_key]
        if not matching_keys:
            return False, "Invalid API key"
        return True, matching_keys[0]

    def record_usage(self, key_info):
        self.data["usage"].append({"name": key_info["name"], "time": time.time()})
        self.save_data()

    def add_request(self, params):
        shared_params = {k: v for k, v in params.items() if k != "prompt"}
        shared_params["model"] = self.model

        event = Event()
        value = {"prompt": params["prompt"], "event": event, "response": None}

        self.requests_queue.put((shared_params, value))

        return event, value

    def package_response(self, event, value):
        # Wait for the event to be set by the request processing thread.
        event.wait()
        # Once the event is set, the response is ready in the value object.
        return value["response"], 200

    def request_openai_api(self, shared_params, prompts):
        return openai.Completion.create(
            prompt=prompts,
            **shared_params
        )

    def process_request_batch(self, key, shared_params, values):
        prompts = [value["prompt"] for value in values]
        response = self.request_openai_api(shared_params, prompts)

        n = shared_params.get("n", 1)
        choices = response["choices"]
        grouped_choices = [choices[i:i + n] for i in range(0, len(choices), n)]

        for value, group in zip(values, grouped_choices):
            value["response"] = {"choices": group}
            value["event"].set()

    def _process_requests(self):
        while True:
            shared_params, value = self.requests_queue.get()
            prompt = value["prompt"]
            response = self.request_openai_api(shared_params, prompt)

            # Now we directly save the response into the value object
            value["response"] = response
            value["event"].set()  # Signal that the response is ready

            self.requests_queue.task_done()

    def run(self):
        request_thread = Thread(target=self._process_requests, daemon=True)
        request_thread.start()
