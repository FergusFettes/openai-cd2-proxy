import os
import json
import time
import subprocess
from unittest.mock import patch
import requests
import asyncio
import aiohttp

import pytest

from main import app


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
def test_server():
    # Assuming your test server uses a specific data.json and lives in the same directory...
    test_server_data_file = 'data.json'

    # Define the content for your test server's data.json file
    server_data = {
        "api_keys": [
            {"name": "test_0", "api_key": "test_api_key_0"},
            {"name": "test_1", "api_key": "test_api_key_1"},
            {"name": "test_2", "api_key": "test_api_key_2"},
            {"name": "test_3", "api_key": "test_api_key_3"},
            {"name": "test_4", "api_key": "test_api_key_4"},
            {"name": "test_5", "api_key": "test_api_key_5"},
            {"name": "test_6", "api_key": "test_api_key_6"},
            {"name": "test_7", "api_key": "test_api_key_7"},
            {"name": "test_8", "api_key": "test_api_key_8"},
            {"name": "test_9", "api_key": "test_api_key_9"},
        ],
        "usage": []
    }

    # Write the test server's data.json file before starting the server
    with open(test_server_data_file, 'w') as f:
        json.dump(server_data, f)

    # Start the server as previously described
    server = subprocess.Popen(["uvicorn", "mock_openai_server:app"])
    time.sleep(2)
    yield server
    server.terminate()
    server.wait()

    os.remove(test_server_data_file)


def test_end_to_end_valid_request(client, test_server):
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


def test_multiple_users_different_api_keys(client, test_server):
    """Test that multiple users with different API keys get appropriate responses."""

    user_responses = []  # Collect responses for verification

    for i in range(3):  # We added three API keys in the test_server fixture
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


def test_multiple_users_different_api_keys_different_params(client, test_server):
    """
    Test that multiple users with different API keys get appropriate responses.
    Since this test is ran synchronously, we dont get to see batching in action--
    each request is processed one at a time.
    """
    response = requests.get('http://localhost:8000/v1/clear')
    assert response.status_code == 200

    user_responses = []  # Collect responses for verification
    user_params = []

    for i in range(10):  # We added three API keys in the test_server fixture
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
    # Just make a request to the mock server at localhost:8000/counter to get the count
    response = requests.get('http://localhost:8000/v1/counter')
    assert response.status_code == 200
    assert response.json()['counter'] == 10


# async def post_prompt_async(session, api_key, user_prompt, params):
#     url = 'http://localhost:5000/v1/completions'  # Swap with your actual Flask app URL
#     headers = {"Authorization": f"Bearer {api_key}"}
#
#     async with session.post(url, headers=headers, json=params) as response:
#         response_json = await response.json()
#         return response_json, response.status
#
#
# async def test_multiple_users_diff_api_keys_concurrent():
#     tasks = []
#     user_params = []
#
#     # Prepare parameters for all users
#     for i in range(10):
#         user_prompt = f'prompt for user {i}'
#         if i % 2 == 0:
#             params = {
#                 "prompt": user_prompt,
#                 "max_tokens": 10,
#                 "n": 1,
#                 "temperature": 0.7,
#                 "stop": ["wut"]
#             }
#         else:
#             params = {
#                 "prompt": user_prompt,
#                 "max_tokens": i,
#                 "n": 1,
#                 "temperature": float(i) / 10,
#                 "stop": ["\n"]
#             }
#         user_params.append(params)
#
#     # Start an aiohttp session
#     async with aiohttp.ClientSession() as session:
#         # Create tasks for concurrent execution
#         for i in range(10):
#             task = post_prompt_async(
#                 session,
#                 f'test_api_key_{i}',
#                 user_params[i]['prompt'],
#                 user_params[i]
#             )
#             tasks.append(task)
#
#         # Run all the requests concurrently
#         responses = await asyncio.gather(*tasks)
#
#     # Process the responses
#     for idx, (response_json, status_code) in enumerate(responses):
#         assert status_code == 200
#         assert response_json['choices'][0]['text'].split('||')[0] == f"prompt for user {idx}"
#         # You can continue with the rest of your assertions here
#
#
# @pytest.mark.asyncio
# async def test_concurrent_requests(client, test_server):
#     await test_multiple_users_diff_api_keys_concurrent()
