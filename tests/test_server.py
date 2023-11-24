import os
import json
import time
import subprocess
from unittest.mock import patch
import requests
import asyncio
import aiohttp

import pytest

from openai_proxy.main import app
from openai_proxy.models import APIKey, db


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with patch.dict('os.environ', {
        'OCP_OPENAI_API_KEY': 'test_api_key_0',
        'OCP_OPENAI_API_BASE': 'http://localhost:8000'
    }):
        with app.test_client() as client:
            yield client


def test_authorization_header_missing(client):
    """Test API request without valid Authorization header."""
    response = client.post(
        '/v1/completions',
        json={"prompt": "hello"},
        headers={"Authorization": None}
    )
    assert response.status_code == 401
    assert response.json.get('error') == "Invalid API key"


def test_invalid_api_key(client):
    """Test API request with invalid API key."""
    response = client.post(
        '/v1/completions',
        json={"prompt": "hello"},
        headers={"Authorization": "Bearer invalid_key"}
    )
    assert response.status_code == 401
    assert response.json['error'] == "Invalid API key"


def test_missing_prompt(client):
    """Test API request with missing prompt."""
    valid_api_key = 'some_valid_api_key'
    response = client.post(
        '/v1/completions',
        json={"not_prompt": "hello"},
        headers={"Authorization": f"Bearer {valid_api_key}"}
    )
    assert response.status_code == 400
    assert response.json['error'] == "prompt is required"


@pytest.fixture(scope="session")
def mock_server():
    # Add api keys to the db
    for i in range(10):
        APIKey.create(name=f'test_api_key_{i}', api_key=f'test_api_key_{i}')
    db.commit()

    # Start the server as previously described
    server = subprocess.Popen(["uvicorn", "mock_openai_server:app"])
    time.sleep(2)
    yield server
    server.terminate()
    server.wait()

    for i in range(10):
        APIKey.delete().where(APIKey.name == f'test_api_key_{i}').execute()
    db.commit()


def test_end_to_end_valid_request(client, mock_server):
    """Test a valid API request end-to-end."""
    valid_api_key = 'test_api_key_0'

    response = client.post(
        '/v1/completions',
        json={"prompt": "test prompt"},
        headers={"Authorization": f"Bearer {valid_api_key}"}
    )

    assert response.status_code == 200
    # The exact assertion here depends on how the test server is echoing back the request
    assert response.json['choices'][0]['text'].split('||')[0] == "test prompt"


def test_multiple_users_different_api_keys(client, mock_server):
    """Test that multiple users with different API keys get appropriate responses."""

    user_responses = []  # Collect responses for verification

    for i in range(3):  # We added three API keys in the mock_server fixture
        api_key = f'test_api_key_{i}'
        user_prompt = f'prompt for user {i}'

        response = client.post(
            '/v1/completions',
            json={"prompt": user_prompt},
            headers={"Authorization": f"Bearer {api_key}"}
        )

        user_responses.append({
            "status_code": response.status_code,
            "api_key": api_key,
            "response_text": response.json['choices'][0]['text'].split('||')[0],
        })

    # Assert that each user received a 200 status code and the correct response
    for user_response in user_responses:
        assert user_response['status_code'] == 200
        assert user_response['response_text'] == f"prompt for user {user_responses.index(user_response)}"


def test_multiple_users_different_api_keys_different_params(client, mock_server):
    """
    Test that multiple users with different API keys get appropriate responses.
    Since this test is ran synchronously, we dont get to see batching in action--
    each request is processed one at a time.
    """
    response = requests.get('http://localhost:8000/v1/clear')
    assert response.status_code == 200

    user_responses = []  # Collect responses for verification
    user_params = []

    for i in range(10):  # We added three API keys in the mock_server fixture
        api_key = f'test_api_key_{i}'
        user_prompt = f'prompt for user {i}'
        # If i is even, use the default params
        if i % 2 == 0:
            params = {
                "max_tokens": 10,
                "n": 1,
                "temperature": 0.7,
                "stop": ["wut"]
            }
        else:
            params = {
                "max_tokens": i,
                "n": 1,
                "temperature": float(i) / 10,
                "stop": ["\n"]
            }
        user_params.append(params)

        response = client.post(
            '/v1/completions',
            json={"prompt": user_prompt, **params},
            headers={"Authorization": f"Bearer {api_key}"}
        )

        user_responses.append({
            "status_code": response.status_code,
            "api_key": api_key,
            "response_text": response.json['choices'][0]['text'].split('||')[0],
            "response_params": json.loads(response.json['choices'][0]['text'].split('||')[1])
        })

    # Assert that each user received a 200 status code and the correct response
    # The response will contain the params as well as the prompt
    for user_response in user_responses:
        assert user_response['status_code'] == 200
        assert user_response['response_text'] == f"prompt for user {user_responses.index(user_response)}"
        assert user_response['response_params'] == user_params[user_responses.index(user_response)]

    # Count the number of times the server was called
    # Just make a request to the mock_server server at localhost:8000/counter to get the count
    response = requests.get('http://localhost:8000/v1/counter')
    assert response.status_code == 200
    assert response.json()['counter'] == 10


@pytest.fixture(scope="session")
def flask_server(mock_server):
    # Define the env vars
    env = os.environ.copy()
    env['OCP_OPENAI_API_KEY'] = 'test_api_key_0'
    env['OCP_OPENAI_ORG'] = 'test_org'
    env['OCP_OPENAI_API_BASE'] = 'http://localhost:8000/v1'
    # Configure to use test environment variables if necessary
    # Start the Flask app in the background
    server = subprocess.Popen(["flask", "--app", "main:app", "run", "--port=5000"], env=env)
    time.sleep(5)
    yield server
    server.terminate()
    server.wait()


@pytest.mark.asyncio
async def test_concurrent_requests(flask_server):
    response = requests.get('http://localhost:8000/v1/clear')
    assert response.status_code == 200

    user_params = []

    # Prepare parameters for all users
    for i in range(4):
        user_prompt = f'prompt for user {i}'
        if i % 2 == 0:
            params = {
                "prompt": user_prompt,
                "max_tokens": 10,
                "n": 1,
                "temperature": 0.7,
                "stop": ["wut"]
            }
        else:
            params = {
                "prompt": user_prompt,
                "max_tokens": i,
                "n": 1,
                "temperature": float(i) / 10,
                "stop": ["\n"]
            }
        user_params.append(params)

    # Perform asynchronous requests using aiohttp
    async with aiohttp.ClientSession() as session:
        # Generate a list of coroutine function calls for concurrent requests
        tasks = [
            asyncio.create_task(  # Create a task for each coroutine
                session.post(
                    'http://localhost:5000/v1/completions',
                    json={**user_params[i]},
                    headers={'Authorization': f'Bearer test_api_key_{i}'}
                )
            )
            for i in range(4)
        ]

        responses = await asyncio.gather(*tasks)  # Waits for all tasks to complete

        # Verify the results
        for response in responses:
            assert response.status == 200
            data = await response.json()
            response_text = data['choices'][0]['text'].split('||')[0]
            assert response_text.startswith('prompt for user')

    # Clean up tasks
    for task in tasks:
        task.cancel()

    # Count the number of times the server was called
    # Just make a request to the mock_server server at localhost:8000/counter to get the count
    response = requests.get('http://localhost:8000/v1/counter')
    assert response.status_code == 200
    assert response.json()['counter'] < 4
