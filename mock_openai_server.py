from typing import Optional, Union, List
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Mock response simulating the structure of an OpenAI completion response
MOCK_RESPONSE = {
    "id": "mock-id",
    "object": "text_completion",
    "created": 1234567890,
    "model": "code-davinci-002",
    "choices": [
        {
            "text": "The quick brown fox jumps over the lazy dog.",
            "index": 0,
            "logprobs": None,
            "finish_reason": "length"
        }
    ],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 10,
        "total_tokens": 20
    }
}

# You can set this environment variable before running the server
# For fixed response: export RESPONSE_MODE="fixed"
# For echo response: export RESPONSE_MODE="echo"
RESPONSE_MODE = os.getenv("RESPONSE_MODE", "echo")


class CompletionRequest(BaseModel):
    prompt: Union[List[str], str]
    max_tokens: Optional[int] = None
    n: Optional[int] = None
    stop: Optional[str] = None
    temperature: Optional[float] = None


def make_echo_response(prompts):
    """
    For every prompt, add a choice where the text is the prompt.
    """
    if isinstance(prompts, str):
        prompts = [prompts]

    mock_base = MOCK_RESPONSE.copy()
    mock_base["choices"] = []
    for i, prompt in enumerate(prompts):
        mock_base["choices"].append({
            "text": prompt,
            "index": i,
            "logprobs": None,
            "finish_reason": "length"
        })
    return mock_base


@app.post("/v1/completions")
def handle_request(completion_request: CompletionRequest):
    print("Processing request.")
    if RESPONSE_MODE == "fixed":
        print("Returning fixed response")
        return MOCK_RESPONSE
    elif RESPONSE_MODE == "echo":
        print("Returning echo response")
        return make_echo_response(completion_request.prompt)
    else:
        raise HTTPException(status_code=500, detail="Invalid RESPONSE_MODE set in environment")
