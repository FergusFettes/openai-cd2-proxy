import uuid
import time
from flask import Flask, jsonify, request
from flask_cors import CORS
from sys import argv
from threading import Lock
from uuid import uuid4

from openai_proxy.request_handler import RequestHandler
from openai_proxy.models import Usage, APIKey, db
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

    if not api_key_full.startswith("Bearer "):
        return jsonify({"error": "Invalid API key"}), 401
    api_key = api_key_full[7:]

    try:
        key_info = APIKey.filter(APIKey.api_key == api_key).first()
    except APIKey.DoesNotExist:
        return jsonify({"error": "Invalid API key"}), 401

    Usage.create(name=key_info.name, time=time.time())
    db.commit()

    logger.debug(f"Adding request: {params}")
    event, value = request_handler.add_request(params)
    response, status_code = request_handler.package_response(event, value)
    logger.debug(f"Response: {response}")
    return jsonify(response), status_code


import typer

cli = typer.Typer()


@cli.command("add-key")
def add_key(name: str, key: str = None):
    api_key = key or str(uuid4())
    try:
        APIKey.create(name=name, api_key=api_key)
        db.commit()
        typer.echo(f"Added key for {name}: {api_key}")
    except Exception:
        typer.echo(f"Key for {name} already exists")


@cli.command("update-key")
def update_key(name: str):
    api_key = str(uuid4())
    try:
        key = APIKey.get(APIKey.name == name)
        key.api_key = str(uuid.uuid4())
        key.save()
        db.commit()
        typer.echo(f"Updated key for {name}: {api_key}")
    except APIKey.DoesNotExist:
        typer.echo(f"Key for {name} does not exist")


@cli.command("delete-key")
def delete_key(name: str):
    try:
        key = APIKey.get(APIKey.name == name)
        key.delete_instance()
        db.commit()
        typer.echo(f"Deleted key for {name}")
    except APIKey.DoesNotExist:
        typer.echo(f"Key for {name} does not exist")


@cli.command("list-keys")
def list_keys():
    for key in APIKey.select():
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
