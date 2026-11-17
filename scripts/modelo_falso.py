"""Modelo falso (compatível com a API da NVIDIA/OpenAI) só para TESTES, sem chave.
Responde de forma simulada. Uso: python modelo_falso.py  (porta 9099)
No produto final isto fica desligado: o Hermes usa a API real da NVIDIA."""
import json
import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()


def resposta(msgs):
    ultimo = next((m for m in reversed(msgs) if m.get("role") == "user"), {})
    c = ultimo.get("content", "")
    if isinstance(c, list):
        c = " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    n = sum(1 for m in msgs if m.get("role") == "user")
    return f"[modelo falso] Mensagens suas nesta conversa: {n}. Última: {c[-120:]}"


@app.get("/v1/models")
def modelos():
    return {"data": [{"id": "nvidia/nemotron-3-ultra-550b-a55b"}]}


@app.post("/v1/chat/completions")
async def chat(req: Request):
    corpo = await req.json()
    texto = resposta(corpo.get("messages", []))
    base = {"id": "falso-1", "object": "chat.completion", "created": int(time.time()),
            "model": corpo.get("model", "falso")}
    if not corpo.get("stream"):
        return JSONResponse({**base, "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": texto}}],
                             "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}})

    def fluxo():
        pedacos = [texto[i:i + 12] for i in range(0, len(texto), 12)]
        for p in pedacos:
            d = {**base, "object": "chat.completion.chunk",
                 "choices": [{"index": 0, "delta": {"content": p}, "finish_reason": None}]}
            yield f"data: {json.dumps(d)}\n\n"
        d = {**base, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
             "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}}
        yield f"data: {json.dumps(d)}\n\ndata: [DONE]\n\n"
    return StreamingResponse(fluxo(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9099, log_level="warning")

