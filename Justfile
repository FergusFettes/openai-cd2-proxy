all:
  poetry install

mock:
  poetry run uvicorn mock_openai_server:app --reload

# run:
# poetry run uvicorn openai_proxy.main:app --reload --port=5000

run:
  poetry run python openai_proxy/main.py

add:
  poetry run main add-key --key test_api_key test

test:
  curl -X POST http://localhost:5000/v1/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test_api_key" \
  -d '{"prompt": "Hello World", "max_tokens": 60}'

usage:
  curl -X GET http://localhost:5000/v1/usage \
  -H "Authorization: Bearer test_api_key"

leaderboard:
  curl -X GET http://localhost:5000/v1/leaderboard \
  -H "Authorization: Bearer test_api_key"

leaderboard_toggle:
  curl -X GET http://localhost:5000/v1/leaderboard_toggle \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test_api_key"

test_back:
  curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test_api_key" \
  -d '{"prompt": "Hello World", "max_tokens": 60}'

test_many:
  # With list of prompts
  curl -X POST http://localhost:5000/v1/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test_api_key" \
  -d '{"prompt": ["Hello World", "This is a test"], "max_tokens": 60}'

pytest:
  poetry run pytest

start:
  docker-compose up --build

start-tests:
  docker-compose --profile test up --exit-code-from tests --abort-on-container-exit
