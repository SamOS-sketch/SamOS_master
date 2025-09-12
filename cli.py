
# cli.py (project root)
import sys
import argparse
from typing import Optional
from dotenv import load_dotenv

# Ensure project root is on sys.path (usually already is when run from root)
# but this keeps things robust if launched differently.
# If you prefer, you can remove these two lines.
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from samos.runtime.event_logger import EventLogger
from router import Router  # project-root/router.py


def main(argv: Optional[list] = None) -> int:
    load_dotenv()  # so SAM_IMAGE_PROVIDER / REFERENCE_IMAGE_ALPHA work from .env

    parser = argparse.ArgumentParser(
        prog="samos",
        description="SamOS CLI — Phase A4 Image Layer"
    )
    parser.add_argument(
        "text",
        nargs="+",
        help='Command text, e.g. Image: "a sunrise over London"'
    )
    parser.add_argument(
        "--img-provider",
        choices=["openai", "comfyui", "stub"],
        help="Override image provider (default from SAM_IMAGE_PROVIDER or 'openai')"
    )
    parser.add_argument(
        "--size",
        default="1024x1024",
        help="Image size (e.g. 512x512, 1024x1024). Default: 1024x1024"
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Optional session ID to include in logs"
    )

    args = parser.parse_args(argv)
    text = " ".join(args.text)

    logger = EventLogger()
    router = Router(event_logger=logger)

    result = router.route(
        text,
        img_provider=args.img_provider,
        size=args.size,
        session_id=args.session_id,
    )

    status = result.get("status")
    if status == "ok":
        url = result.get("url", "")
        provider = result.get("provider", "")
        ref = result.get("reference_used")
        print(f"[OK] Provider={provider}  URL={url}")
        if ref:
            print(f"ReferenceImageAlpha used: {ref}")
        return 0
    else:
        print(f"[FAIL] {result.get('error','unknown error')}")
        return 1


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main())
