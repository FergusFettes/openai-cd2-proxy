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
            {"name": "test_0", "api_key": "test_api_key_0"}
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

    # Optionally remove or archive the modified data.json file
    # os.remove(test_server_data_file)  # Uncomment if you want to delete the file after tests.


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
