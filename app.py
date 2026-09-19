"""Serves index.html and one /ask endpoint. Run: python app.py"""

import os
import socket

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent import decide

app = FastAPI()
HERE = os.path.dirname(__file__)


class Ask(BaseModel):
    question: str


@app.get("/")
def home():
    return FileResponse(os.path.join(HERE, "index.html"))


@app.post("/ask")
def ask(body: Ask):
    return decide(body.question)


if __name__ == "__main__":
    import uvicorn

    requested_port = int(os.environ.get("PORT", "8000"))
    port = requested_port
    while True:
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
                break
            except OSError:
                if requested_port != 8000:
                    raise
                port += 1

    print(f"PolicyLens running at http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
