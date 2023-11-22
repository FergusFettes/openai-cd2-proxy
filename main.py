from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request
from flask_cors import CORS
import hashlib
import json
import openai
from os import getenv
from sys import argv
from threading import Event, Lock, Thread
import time
from uuid import uuid4

app = Flask(__name__)
CORS(app)
openai.api_key = getenv("OCP_OPENAI_API_KEY")
openai.organization = getenv("OCP_OPENAI_ORG")
openai.api_base = getenv("OCP_OPENAI_API_BASE")

pending_requests = {}
lock = Lock()


def load_data():
    global data
    try:
        with open("data.json") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"api_keys": [], "usage": []}


load_data()


def validate_api_key(api_key_full):
    if not api_key_full.startswith("Bearer "):
        return False, "Invalid API key"
    api_key = api_key_full[7:]
    load_data()
    matching_keys = [key for key in data["api_keys"] if key["api_key"] == api_key]
    if not matching_keys:
        return False, "Invalid API key"
    return True, matching_keys[0]


def record_usage(key_info):
    with open("data.json", "w") as f:
        data["usage"].append({"name": key_info["name"], "time": time.time()})
        json.dump(data, f)


def package_response(event, key, params):
    event.wait()
    with lock:
        for value in pending_requests[key]["values"]:
            if value["prompt"] == params["prompt"]:
                return jsonify(value["response"])
    return jsonify({"error": "Unable to process request"}), 500


@app.route("/v1/completions", methods=["POST"])
def handle_request():
    params = request.get_json()

    if "prompt" not in params:
        return jsonify({"error": "prompt is required"}), 400

    api_key_full = request.headers.get("Authorization")
    valid, result = validate_api_key(api_key_full)
    if not valid:
        return jsonify({"error": result}), 401
    key_info = result

    record_usage(key_info)
    params["model"] = "code-davinci-002"

    shared_params = {k: v for k, v in params.items() if k != "prompt"}

    event = Event()
    sha256 = hashlib.sha256()
    sha256.update(json.dumps(tuple(sorted(params.items()))).encode("utf-8"))
    key = sha256.digest()
    value = {"prompt": params["prompt"], "event": event}

    with lock:
        if key not in pending_requests:
            pending_requests[key] = {"shared_params": shared_params, "values": [value]}
        else:
            pending_requests[key]["values"].append(value)

    return package_response(event, key, params)


def handle_pending_requests():
    while True:
        with lock:
            if not pending_requests:
                continue

            key = next(iter(pending_requests))
            shared_params = pending_requests[key]["shared_params"]
            values = pending_requests[key]["values"]

            prompts = [value["prompt"] for value in values]

            response = openai.Completion.create(
                prompt=prompts,
                **shared_params
            )

            if "n" in shared_params:
                n = shared_params["n"]
            else:
                n = 1
            choices = response["choices"]
            grouped_choices = [choices[i:i + n] for i in range(0, len(choices), n)]

            for value, choices in zip(values, grouped_choices):
                value["response"] = {"choices": choices}
                value["event"].set()

            key_to_delete = key

        time.sleep(3)

        with lock:
            del pending_requests[key_to_delete]


import typer

cli = typer.Typer()


def save_data():
    with open("data.json", "w") as f:
        json.dump(data, f)


@cli.command("add-key")
def add_key(name: str):
    api_key = str(uuid4())
    data["api_keys"].append({"name": name, "api_key": api_key})
    save_data()
    typer.echo(f"Added key {api_key} for {name}")


@cli.command("delete-key")
def delete_key(name: str):
    data["api_keys"] = [key for key in data["api_keys"] if key["name"] != name]
    save_data()
    typer.echo(f"Deleted key for {name}")


@cli.command("list-keys")
def list_keys():
    for key in data["api_keys"]:
        typer.echo(f"{key['name']}: {key['api_key']}")


def run_server():
    Thread(target=handle_pending_requests, daemon=True).start()
    app.run()


if __name__ == "__main__":
    if len(argv) == 1:
        run_server()
    else:
        cli()
