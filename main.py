import modal
import io
import os
import logging
from fastapi import UploadFile, File, HTTPException, Header
from fastapi.responses import Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

image = (
    modal.Image.debian_slim()
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "rembg[cpu]",
        "pillow",
        "python-multipart",
        "fastapi",
    )
    .run_commands(
        "python -c \"from rembg import new_session; new_session('birefnet-general-lite')\""
    )
)

app = modal.App("bg-service", image=image)


@app.cls(
    cpu=2,
    memory=1024,
    scaledown_window=300,
    min_containers=1, 
    secrets=[modal.Secret.from_name("bg-service-secrets")]
)
class BackgroundRemover:
    @modal.enter()
    def load_model(self):
        from rembg import new_session
        logger.info("Loading rembg model, please wait...")
        self.session = new_session("birefnet-general-lite")
        logger.info("Model ready")

    @modal.fastapi_endpoint(method="GET")
    def health(self):
        return {"status": "ok"}

    @modal.fastapi_endpoint(method="POST")
    async def remove_background(
        self,
        file: UploadFile = File(...),
        x_api_key: str = Header(None)
    ):
        expected_key = os.environ.get("INTERNAL_API_KEY")
        if expected_key and x_api_key != expected_key:
            raise HTTPException(status_code=401, detail="Unauthorized")

        allowed_types = ["image/png", "image/jpeg", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Unsupported type: {file.content_type}")

        contents = await file.read()

        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large, max 10MB")

        try:
            from rembg import remove
            from PIL import Image

            logger.info(f"Processing: {file.filename} ({len(contents)} bytes)")

            output_bytes = remove(contents, session=self.session)

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