# SamOS\\nMinimal runtime for Phase 10.

\## Build a Skill in 60 seconds

# SamOS_master

![Build Status](https://img.shields.io/badge/tests-passing-brightgreen)
![Phase](https://img.shields.io/badge/phase-10%20✔-blue)
![Version](https://img.shields.io/badge/version-v0.1.0--phase10-orange)
![License](https://img.shields.io/badge/license-private-lightgrey)

---

Minimal runtime for Phase 10.  
SamOS is evolving through structured development phases, each tagged in GitHub for clarity.  



Create `my\_skill.py`:

```python

from samos.runtime.models import UserMessage, Response, Context



class MySkill:

&nbsp; name = "my\_skill"

&nbsp; def supports(self, msg: UserMessage, ctx: Context) -> bool:

&nbsp;   return msg.text.strip().lower().startswith("do:")

&nbsp; def run(self, msg: UserMessage, ctx: Context) -> Response:

&nbsp;   task = msg.text.split(":",1)\[1].strip() or "(nothing)"

&nbsp;   return Response(text=f"{ctx.soulprint.voice\_tag()}: doing {task}")

## Drift Detection (Phase A8)

Every generated image is compared to the reference image (`REFERENCE_IMAGE_ALPHA`) to enforce
**"Sam remembers Sam"**.

- **Drift score:** A float in [0,1], where 0 = identical, 1 = maximum drift.
- **Methods:** CLIP embeddings (preferred), pHash, SSIM. Auto-fallback if unavailable.
- **Threshold:** Controlled by `DRIFT_THRESHOLD` (default 0.35).
- **On breach:**
  - Event `image.drift.detected` is logged
  - An `emm.onebounce` event is emitted
  - `/metrics` counter `image_drift_detected_count` increments
  - Drift score is persisted to the DB

### Example .env

### Drift detection (Phase A8a)

Drift scoring is centralized in `samos/providers/image_base.py`.

Env controls:
- `DRIFT_METHOD` — one of `auto|clip|phash|ssim` (default: `auto`)
  - `auto` tries **CLIP → pHash → SSIM** in that order, falling back if a method isn’t available.
- `DRIFT_THRESHOLD` — float in `[0..1]` (default: `0.35`). If `drift_score > threshold`, we:
  - increment `image_drift_detected_count` (in `/metrics`)
  - emit events: `image.drift.detected` and `emm.onebounce`

Every image generation persists metadata (incl. `drift_score`) and fires `image.generate.ok` or `image.generate.fail`.

### Drift detection (Phase A8a)

Drift scoring is centralized in `samos/providers/image_base.py`.

**Env controls**
- `DRIFT_METHOD` — `auto|clip|phash|ssim` (default: `auto`).  
  `auto` tries **CLIP → pHash → SSIM**, falling back if unavailable.
- `DRIFT_THRESHOLD` — float `[0..1]` (default: `0.35`).  
  If `drift_score > threshold`, we increment `image_drift_detected_count` and emit
  `image.drift.detected` + `emm.onebounce`.

**Behavior**
- Every generation persists metadata (incl. `drift_score`) and emits `image.generate.ok` or `image.generate.fail`.
- File URLs are normalized (e.g., `file:///D:/...`).
- `meta.reference_used` is always present (true/false).
