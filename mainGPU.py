"""
Run this script inside rembg conda environment.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from rembg import remove, new_session
from PIL import Image
from dotenv import load_dotenv
import io
import os
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "http://localhost:3000")
GPU_MEM_LIMIT_GB = float(os.getenv("GPU_MEM_LIMIT_GB", "9"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

providers = [
    (
        "CUDAExecutionProvider",
        {
            "device_id": 0,
            "arena_extend_strategy": "kSameAsRequested",
            "gpu_mem_limit": int(GPU_MEM_LIMIT_GB * 1024 * 1024 * 1024),
            "cudnn_conv_algo_search": "HEURISTIC",
        },
    ),
    "CPUExecutionProvider",
]

logger.info(f"Loading rembg model, please wait... (GPU mem cap: {GPU_MEM_LIMIT_GB} GB)")
session = new_session("birefnet-general-lite", providers=providers)
logger.info("Model ready")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/remove-background")
async def remove_background(file: UploadFile = File(...)):
    allowed_types = ["image/png", "image/jpeg", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Unsupported type: {file.content_type}")

    contents = await file.read()

    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large, max 10MB")

    try:
        logger.info(f"Processing: {file.filename} ({len(contents)} bytes)")

        output_bytes = remove(contents, session=session)

        img = Image.open(io.BytesIO(output_bytes))
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        logger.info(f"Done: {file.filename}")
        return Response(content=buffer.read(), media_type="image/png")

    except Exception as e:
        logger.error(f"Failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Background removal failed")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 5003))
    uvicorn.run(app, host="0.0.0.0", port=port)