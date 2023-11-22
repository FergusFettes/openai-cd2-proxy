from os import getenv
import hashlib
import json
import time
from threading import Event, Lock, Thread
import openai

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
        self.pending_requests = {}
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
        sha256 = hashlib.sha256()
        sha256.update(json.dumps(tuple(sorted(params.items()))).encode("utf-8"))
        key = sha256.digest()
        value = {"prompt": params["prompt"], "event": event}

        with self.lock:
            if key not in self.pending_requests:
                self.pending_requests[key] = {
                    "shared_params": shared_params,
                    "values": [value]
                }
            else:
                self.pending_requests[key]["values"].append(value)

        return event, key

    def package_response(self, event, key, params):
        event.wait()
        with self.lock:
            print(f"In package_response {self.pending_requests}")
            for value in self.pending_requests[key]["values"]:
                if value["prompt"] == params["prompt"]:
                    return value["response"], 200
        return {"error": "Unable to process request"}, 500

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
            with self.lock:
                keys_to_delete = []
                print(f"In _process_requests {self.pending_requests}")
                for key, details in self.pending_requests.items():
                    shared_params = details["shared_params"]
                    values = details["values"]
                    self.process_request_batch(key, shared_params, values)
                    keys_to_delete.append(key)

            time.sleep(3)

            with self.lock:
                for key in keys_to_delete:
                    del self.pending_requests[key]

    def run(self):
        request_thread = Thread(target=self._process_requests, daemon=True)
        request_thread.start()
