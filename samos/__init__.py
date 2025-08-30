# samos/__init__.py
try:
    from ._version import version as __version__  # written at build time
except Exception:
    try:
        from importlib.metadata import version as _pkg_version
        __version__ = _pkg_version("samos")        # works in editable installs
    except Exception:
        __version__ = "0.0.0+unknown"              # fallback when no metadata
