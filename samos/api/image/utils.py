import base64, os, uuid, pathlib, datetime
from typing import Tuple

_GEN_DIR = pathlib.Path(__file__).resolve().parent.parent / "generated"
_GEN_DIR.mkdir(exist_ok=True)

def _new_filename(ext: str = "png") -> pathlib.Path:
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return _GEN_DIR / f"{stamp}-{uuid.uuid4().hex}.{ext.lstrip('.')}"

def save_image_bytes(data: bytes, ext: str = "png") -> Tuple[str, str]:
    """
    Save raw image bytes to disk and return (absolute_path, file_url).
    """
    path = _new_filename(ext)
    with open(path, "wb") as f:
        f.write(data)
    file_url = path.resolve().as_uri()  # file:///...
    return str(path.resolve()), file_url

def save_base64_image(b64_str: str, ext: str = "png") -> Tuple[str, str]:
    """
    Save a base64-encoded image (no data URL prefix) to disk and return (absolute_path, file_url).
    """
    raw = base64.b64decode(b64_str)
    return save_image_bytes(raw, ext)
