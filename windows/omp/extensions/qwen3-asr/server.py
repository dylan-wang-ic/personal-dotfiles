"""Qwen3-ASR worker: OpenAI-compatible speech-to-text on a loopback port.

Started on demand by the omp extension (extensions/qwen3-asr/index.ts), which proxies port 8765 to it.

POST /v1/audio/transcriptions  (multipart: file, model, response_format, ...)
GET  /v1/models
GET  /health

The `language` form field is deliberately ignored: Qwen3-ASR runs its own language
identification, which is what lets one model handle Chinese with embedded English
words as well as fully English speech.
"""
import io
import os
import threading
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import soundfile as sf
import torch
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from qwen_asr import Qwen3ASRModel

HOST = os.environ.get("QWEN_ASR_HOST", "127.0.0.1")
PORT = int(os.environ.get("QWEN_ASR_PORT", "8766"))
MODEL_ID = os.environ.get("QWEN_ASR_MODEL_ID", "qwen3-asr-0.6b")
MODEL_PATH = os.environ.get("QWEN_ASR_MODEL_PATH", "Qwen/Qwen3-ASR-0.6B")  # Hub id, read from the local cache
DEVICE = os.environ.get("QWEN_ASR_DEVICE", "cuda:0" if torch.cuda.is_available() else "cpu")
DTYPE = torch.bfloat16 if DEVICE.startswith("cuda") else torch.float32
MAX_NEW_TOKENS = int(os.environ.get("QWEN_ASR_MAX_NEW_TOKENS", "1024"))
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # same cap as the OpenAI endpoint

app = FastAPI(title="qwen3-asr")
_model = None
_gpu_lock = threading.Lock()  # one inference at a time on the single GPU


def load_model():
    global _model
    _model = Qwen3ASRModel.from_pretrained(
        MODEL_PATH,
        dtype=DTYPE,
        device_map=DEVICE,
        max_inference_batch_size=1,
        max_new_tokens=MAX_NEW_TOKENS,
    )


def decode_audio(data: bytes):
    """Return (mono float32 samples, sample rate). soundfile first, PyAV for the rest."""
    try:
        wav, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
        return wav.mean(axis=1), sr
    except Exception:
        pass
    import av

    with av.open(io.BytesIO(data)) as container:
        stream = next(s for s in container.streams if s.type == "audio")
        resampler = av.AudioResampler(format="flt", layout="mono", rate=16000)
        chunks = []
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        raise ValueError("no audio decoded")
    return np.concatenate(chunks).astype(np.float32), 16000


@app.get("/health")
def health():
    return {"status": "ok" if _model is not None else "loading", "model": MODEL_ID, "device": DEVICE}


@app.get("/v1/models")
def models():
    return {"object": "list", "data": [{"id": MODEL_ID, "object": "model", "owned_by": "local"}]}


@app.post("/v1/audio/transcriptions")
def transcribe(
    file: UploadFile = File(...),
    model: str = Form(default=MODEL_ID),
    response_format: str = Form(default="json"),
    language: str = Form(default=""),  # accepted, intentionally unused
    prompt: str = Form(default=""),  # accepted, unused
    temperature: str = Form(default=""),  # accepted, unused
):
    if _model is None:
        raise HTTPException(status_code=503, detail="model still loading")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file exceeds 25 MiB")
    try:
        wav, sr = decode_audio(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"cannot decode audio: {exc}")
    duration = len(wav) / sr
    started = time.time()
    with _gpu_lock:
        result = _model.transcribe(audio=(wav, sr), language=None)[0]
    text = (result.text or "").strip()
    print(
        f"[asr] {time.strftime('%H:%M:%S')} audio={duration:.1f}s took={time.time() - started:.2f}s "
        f"lang={(result.language or '?').lower()} hint={language or '-'} fmt={response_format} "
        f"bytes={len(data)} ctype={file.content_type} :: {text[:120]}",
        flush=True,
    )
    if response_format == "text":
        return PlainTextResponse(text)
    body = {"text": text}
    if response_format == "verbose_json":
        body.update(
            task="transcribe",
            language=(result.language or "").lower(),
            duration=round(duration, 3),
            segments=[],
            inference_seconds=round(time.time() - started, 3),
        )
    return JSONResponse(body)


def _exit_with_parent(parent_pid):
    """Never outlive serve.py: if it dies without cleaning up, free the GPU by exiting."""
    import psutil

    while psutil.pid_exists(parent_pid):
        time.sleep(3)
    os._exit(0)


if __name__ == "__main__":
    if os.environ.get("QWEN_ASR_PARENT_PID"):
        threading.Thread(target=_exit_with_parent, args=(int(os.environ["QWEN_ASR_PARENT_PID"]),), daemon=True).start()
    load_model()
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
