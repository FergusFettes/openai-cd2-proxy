from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os

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
RESPONSE_MODE = os.getenv("RESPONSE_MODE", "fixed")


class CompletionRequest(BaseModel):
    prompt: str
    max_tokens: Optional[int] = None
    n: Optional[int] = None
    stop: Optional[str] = None
    temperature: Optional[float] = None


@app.post("/v1/completions")
def handle_request(completion_request: CompletionRequest):
    if RESPONSE_MODE == "fixed":
        return MOCK_RESPONSE
    elif RESPONSE_MODE == "echo":
        # Optionally, process the request to create a tailored response
        return {"received_request": completion_request.dict()}
    else:
        raise HTTPException(status_code=500, detail="Invalid RESPONSE_MODE set in environment")


if __name__ == "__main__":
    import uvicorn
    # The server will run on http://localhost:8000 by default
    uvicorn.run(app, host="0.0.0.0", port=8000)
