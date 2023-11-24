import uuid
from os import getenv
import json
import time
from threading import Event, Lock, Thread
import openai
import queue

from models import APIKey, Usage, db

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

    def delete_api_key(self, name):
        try:
            key = APIKey.get(APIKey.name == name)
            key.delete_instance()
            db.commit()
            return True
        except APIKey.DoesNotExist:
            return False

    def add_api_key(self, name):
        try:
            APIKey.create(name=name)
            db.commit()
            return True
        except Exception:
            return False

    def update_api_key(self, name):
        try:
            key = APIKey.get(APIKey.name == name)
            key.api_key = str(uuid.uuid4())
            key.save()
            db.commit()
            return True
        except APIKey.DoesNotExist:
            return False

    def list_api_keys(self):
        return APIKey.select()

    def validate_api_key(self, api_key_full):
        if not api_key_full.startswith("Bearer "):
            return False, "Invalid API key"
        api_key = api_key_full[7:]

        try:
            key_info = APIKey.get(APIKey.api_key == api_key)
            return True, {
                "name": key_info.name,
                "api_key": key_info.api_key
            }
        except APIKey.DoesNotExist:
            return False, "Invalid API key"

    def record_usage(self, key_info):
        Usage.create(name=key_info["name"], time=time.time())
        db.commit()

    def add_request(self, params):
        shared_params = {k: v for k, v in params.items() if k != "prompt"}
        shared_params["model"] = self.model

        batch_id = self._generate_batch_id(shared_params)

        event = Event()
        value = {"prompt": params["prompt"], "event": event, "response": None}

        print(self.requests_queue.qsize())
        self.requests_queue.put((batch_id, shared_params, value))
        print(self.requests_queue.qsize())

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
        return openai.Completion.create(
            prompt=prompts,
            **shared_params
        )

    def process_request_batch(self, batch_id, shared_params, prompts, values):
        # Request OpenAI API for the batch
        print("Requesting OpenAI API")
        response = self.request_openai_api(shared_params, prompts)

        n = shared_params.get("n", 1)
        choices = response["choices"]
        grouped_choices = [choices[i:i + n] for i in range(0, len(choices), n)]

        for value, group in zip(values, grouped_choices):
            value["response"] = {"choices": group}
            value["event"].set()

    def _process_requests(self):
        while True:
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

            # Here you could insert a delay before processing the next set of batches
            time.sleep(3)  # Adjust the sleep time as needed

    def run(self):
        request_thread = Thread(target=self._process_requests, daemon=True)
        request_thread.start()
