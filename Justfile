mock:
  uvicorn mock_openai_server:app --reload

run_flask:
  flask --app openai_proxy/main:app --debug run

run:
  poetry run python openai_proxy/main.py

test:
  curl -X POST http://localhost:5000/v1/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test_api_key" \
  -d '{"prompt": "Hello World", "max_tokens": 60}'

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
