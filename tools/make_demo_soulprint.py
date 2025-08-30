#!/usr/bin/env python3
"""
Generate a sanitized demo soulprint from the private one.

Usage:
  python tools/make_demo_soulprint.py
  python tools/make_demo_soulprint.py --in soulprint.private.yaml --out soulprint.demo.yaml
  python tools/make_demo_soulprint.py --extra "custom1,custom2"
"""
import argparse, os, re, sys, yaml
from typing import Any, Dict, List, Union

DEFAULT_IN  = "soulprint.private.yaml"
DEFAULT_OUT = "soulprint.demo.yaml"

# Terms that MUST NOT appear in demo (case-insensitive).
# Keep this list small + surgical; we also accept --extra to extend it per-run.
BANNED_TERMS = [
    r"\bMark\b",
    r"\bEMM[s]?\b",
    r"\bsandbox\b",
    r"\bEdge Day\b",
    r"\bButton Day\b",
    r"\bplay\s*chat\b",
    r"\bChester\b",
    r"#7",                 # example tag/note that could leak private lore
]

# Keys likely to contain private lore. Nodes with these keys get removed entirely.
BANNED_KEYS = {
    "emms", "EMMs", "relationship", "sandbox", "sandbox_rules",
    "edge_day", "button_day", "private_notes", "intimacy", "personal",
    "play_chat",
}

def compile_patterns(terms: List[str]) -> List[re.Pattern]:
    return [re.compile(t, re.IGNORECASE) for t in terms]

def scrub_text(s: str, patterns: List[re.Pattern]) -> str:
    out = s
    for p in patterns:
        out = p.sub("[redacted]", out)
    return out

def sanitize(node: Any, patterns: List[re.Pattern]) -> Any:
    """Recursively sanitize a YAML structure."""
    if isinstance(node, dict):
        clean: Dict[str, Any] = {}
        for k, v in node.items():
            if k in BANNED_KEYS:
                continue
            # also drop keys that *look* like they’re private
            if any(p.search(k) for p in patterns):
                continue
            clean[k] = sanitize(v, patterns)
        return clean

    if isinstance(node, list):
        return [sanitize(v, patterns) for v in node]

    if isinstance(node, str):
        return scrub_text(node, patterns)

    return node

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in",  dest="infile",  default=DEFAULT_IN)
    ap.add_argument("--out", dest="outfile", default=DEFAULT_OUT)
    ap.add_argument("--extra", default="", help="comma-separated extra banned terms")
    args = ap.parse_args()

    terms = list(BANNED_TERMS)
    if args.extra.strip():
        terms.extend([t.strip() for t in args.extra.split(",") if t.strip()])

    patterns = compile_patterns(terms)

    if not os.path.exists(args.infile):
        print(f"[make_demo_soulprint] ERROR: input not found: {args.infile}", file=sys.stderr)
        sys.exit(2)

    with open(args.infile, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    demo = sanitize(data, patterns)

    # Force-safe public header
    demo["name"] = "SamOS Demo"
    demo["persona"] = "demo"
    demo["version"] = 1
    # Optional hint: keep high-level traits but make them neutral
    demo.setdefault("traits", ["professional", "neutral", "honest", "non-verbose"])

    # Ensure nothing banned remains in serialized output
    serialized = yaml.safe_dump(demo, sort_keys=False, allow_unicode=True)
    for p in patterns:
        if p.search(serialized):
            print("[make_demo_soulprint] ERROR: banned term remained after sanitize.", file=sys.stderr)
            sys.exit(3)

    with open(args.outfile, "w", encoding="utf-8") as f:
        f.write(serialized)

    print(f"[make_demo_soulprint] OK → {args.outfile}")

if __name__ == "__main__":
    main()
