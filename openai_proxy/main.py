from flask import Flask, jsonify, request
from flask_cors import CORS
from sys import argv
from threading import Lock
from uuid import uuid4

from openai_proxy.request_handler import RequestHandler
from openai_proxy.models import Usage
from openai_proxy.utils import logger

app = Flask(__name__)
request_handler = RequestHandler()
CORS(app)

lock = Lock()
logger.debug("Starting server")


@app.route("/v1/completions", methods=["POST"])
def handle_request():
    params = request.get_json()
    if "prompt" not in params:
        return jsonify({"error": "prompt is required"}), 400

    api_key_full = request.headers.get("Authorization")
    valid, result = request_handler.validate_api_key(api_key_full)
    if not valid:
        return jsonify({"error": result}), 401

    key_info = result
    request_handler.record_usage(key_info)

    logger.debug(f"Adding request: {params}")
    event, value = request_handler.add_request(params)
    response, status_code = request_handler.package_response(event, value)
    logger.debug(f"Response: {response}")
    return jsonify(response), status_code


import typer

cli = typer.Typer()


# Optionally takes a string which is the key
@cli.command("add-key")
def add_key(name: str, key: str = None):
    api_key = key or str(uuid4())
    if not request_handler.add_api_key(name, key):
        typer.echo(f"Key for {name} already exists")
    else:
        typer.echo(f"Added key for {name}: {api_key}")


@cli.command("update-key")
def update_key(name: str):
    api_key = str(uuid4())
    if not request_handler.update_api_key(name):
        typer.echo(f"Key for {name} does not exist")
    else:
        typer.echo(f"Updated key for {name}: {api_key}")


@cli.command("delete-key")
def delete_key(name: str):
    if not request_handler.delete_api_key(name):
        typer.echo(f"Key for {name} does not exist")
    else:
        typer.echo(f"Deleted key for {name}")


@cli.command("list-keys")
def list_keys():
    for key in request_handler.list_api_keys():
        typer.echo(f"{key.name}: {key.api_key}")


@cli.command("usage")
def usage():
    typer.echo("Usage:")
    for usage in Usage.select():
        typer.echo(f"{usage.name}: {usage.time}")


def run_server():
    request_handler.run()
    app.run()


if __name__ == "__main__":
    if len(argv) == 1:
        run_server()
    else:
        cli()
