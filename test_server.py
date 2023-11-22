import os
import json
import time
import subprocess
from unittest.mock import patch

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
    assert response.json['choices'][0]['text'] == "test prompt"


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
            "response_text": response.json['choices'][0]['text']
        })

    # Assert that each user received a 200 status code and the correct response
    for user_response in user_responses:
        assert user_response['status_code'] == 200
        assert user_response['response_text'] == f"prompt for user {user_responses.index(user_response)}"
