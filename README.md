SamOS — V1 Release








What is SamOS?

SamOS is a persistent, identity-locked runtime for LLM applications.
It routes to image providers, remembers sessions, logs events & metrics, and enforces identity consistency with drift detection.

V1 Capabilities

Provider routing with fallback (comfyui → openai → stub)

Identity lock + drift scoring (stored in DB)

Sessions, events, metrics

Image APIs:

/image/generate

/image/{id}

/image/{id}/file

/image/latest/file

/events

/metrics

Reproducible DB migrations (Alembic baseline)

File serving (local paths, file://, or redirect)

Quick Start
git clone https://github.com/SamOS-sketch/SamOS_master.git
cd SamOS_master
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
pip install -r requirements.txt

# Bootstrap DB
python tools/db_bootstrap.py

# Start API
uvicorn samos.api.main:app --reload --port 8000


Smoke Test

# Run golden smoke test
powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1


Expected: Smoke OK – image ... saved as smoke.png

API Quick Reference
Sessions

POST /session/start
Returns { "session_id": "uuid" }.

Image

POST /image/generate → generate image

GET /image/{id} → get metadata

GET /image/{id}/file → serve/download file

GET /image/latest/file → most recent file

Events

GET /events → list events (JSON)

Metrics

GET /metrics → counters + gauges

Drift Detection (Phase A8)

Every generated image is compared to the reference (REFERENCE_IMAGE_ALPHA) to enforce
“Sam remembers Sam.”

Drift score: float [0,1] (0 = identical, 1 = max drift)

Methods: CLIP → pHash → SSIM (auto-fallback)

Threshold: DRIFT_THRESHOLD (default 0.35)

On breach:

Log image.drift.detected

Emit emm.onebounce

Increment /metrics counter image_drift_detected_count

Persist drift score in DB

Image Providers & Routing

SamOS can route across providers with fallback.

Primary: IMAGE_PROVIDER

Fallback: IMAGE_PROVIDER_FALLBACK (colon-separated, e.g. comfyui:openai:stub)

Providers:

comfyui — local ComfyUI (or stub/live via COMFYUI_MODE)

openai — gpt-image-1

stub — safe default, always returns a tiny PNG

Environment Variables

Core env vars for V1:

IMAGE_PROVIDER=stub
IMAGE_PROVIDER_FALLBACK=
COMFYUI_URL=http://127.0.0.1:8189
OPENAI_API_KEY=sk-...
DRIFT_METHOD=auto
DRIFT_THRESHOLD=0.35
SAM_STORAGE_DIR=outputs
DATABASE_URL=sqlite:///./samos.db

Troubleshooting

Migrations fail
→ Run python tools/db_bootstrap.py --reset

File not found
→ Ensure SAM_STORAGE_DIR exists or paths are normalized

Drift errors
→ Install extras:

pip install pillow imagehash scikit-image open-clip-torch torch torchvision


ComfyUI not responding
→ Check COMFYUI_URL in .env and confirm ComfyUI is running

Changelog
v1.0.0

First stable release

End-to-end runtime: sessions, images, events, metrics

Provider routing + drift detection

Golden smoke test script added

License

Private / internal only.