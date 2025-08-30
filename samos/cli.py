# samos/cli.py
from __future__ import annotations

import argparse
import os
import sys


def _resolve_app_path() -> str:
    """
    We try a few common locations for the FastAPI app object.
    Returns a uvicorn import target like 'package.module:app'.
    """
    # Preferred modern path
    candidates = [
        "samos.api.main:app",   # e.g. your Phase 4+ layout
        "samos.main:app",       # fallback if you kept it flat
    ]
    for target in candidates:
        try:
            module_path, obj_name = target.split(":")
            mod = __import__(module_path, fromlist=[obj_name])
            getattr(mod, obj_name)  # raises if missing
            return target
        except Exception:
            continue

    sys.stderr.write(
        "[samos] Could not find a FastAPI app. "
        "Expected one of: 'samos.api.main:app' or 'samos.main:app'.\n"
        "Please create an 'app = FastAPI()' in one of those modules, "
        "or update samos/cli.py _resolve_app_path().\n"
    )
    sys.exit(2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="samos",
        description="SamOS CLI — run the API with a chosen persona."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run the SamOS API server")
    run_p.add_argument(
        "--persona",
        choices=["demo", "private"],
        required=True,
        help="Which persona to load (demo is safe/public; private is full context).",
    )
    run_p.add_argument(
        "--host", default=os.getenv("SAMOS_HOST", "127.0.0.1"),
        help="Bind host (default from SAMOS_HOST or 127.0.0.1)."
    )
    run_p.add_argument(
        "--port", type=int, default=int(os.getenv("SAMOS_PORT", "8000")),
        help="Bind port (default from SAMOS_PORT or 8000)."
    )
    run_p.add_argument(
        "--reload", action="store_true",
        help="Enable autoreload (dev only)."
    )

    args = parser.parse_args(argv)

    if args.cmd == "run":
        # Export persona for the app to read
        os.environ["SAMOS_PERSONA"] = args.persona

        # (Optional future: IMAGE_PROVIDER feature flag)
        os.environ.setdefault("IMAGE_PROVIDER", os.getenv("IMAGE_PROVIDER", "stub"))

        target = _resolve_app_path()

        try:
            import uvicorn  # type: ignore
        except Exception:
            sys.stderr.write(
                "[samos] uvicorn is not installed. Install with: pip install 'uvicorn[standard]'\n"
            )
            return 2

        uvicorn.run(
            target,
            host=args.host,
            port=args.port,
            reload=args.reload,
            # You can set log_level here if you like:
            # log_level="info",
        )
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
