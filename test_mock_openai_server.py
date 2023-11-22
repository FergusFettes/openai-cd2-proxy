import pytest
import requests

# Define the base URL for the mock servers
FASTAPI_BASE_URL = "http://localhost:8000/v1/completions"
FLASK_BASE_URL = "http://localhost:5000/v1/completions"


@pytest.mark.parametrize("base_url", [FASTAPI_BASE_URL, FLASK_BASE_URL])
def test_single_prompt_completion(base_url):
    payload = {
        "prompt": "Hello World",
        "max_tokens": 60
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer test_api_key"
    }
    response = requests.post(base_url, json=payload, headers=headers)
    if not response.ok:
        print(response.json())
    assert response.status_code == 200
    assert "choices" in response.json()
    assert len(response.json()["choices"]) == 1
    assert response.json()["choices"][0]["text"] == "Hello World"


# @pytest.mark.parametrize("base_url", [FASTAPI_BASE_URL, FLASK_BASE_URL])
# def test_many_prompts_completion(base_url):
#     payload = {
#         "prompt": ["Hello World", "This is a test"],
#         "max_tokens": 60
#     }
#     headers = {
#         "Content-Type": "application/json",
#         "Authorization": "Bearer test_api_key"
#     }
#     response = requests.post(base_url, json=payload, headers=headers)
#     assert response.status_code == 200
#     assert "choices" in response.json()
#     assert len(response.json()["choices"]) == 2
#     assert response.json()["choices"][0]["text"] == "Hello World"
#     assert response.json()["choices"][1]["text"] == "This is a test"
