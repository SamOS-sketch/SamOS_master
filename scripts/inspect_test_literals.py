import re, pathlib

def dump(label, s: str):
    print(f"\n--- {label} ---")
    print("repr:", repr(s))
    print("codes:", [ord(c) for c in s])

# tests/test_skills.py — find: assert out.text == "..."
skills_src = pathlib.Path("tests/test_skills.py").read_text(encoding="utf-8")
m = re.search(r'assert\s+out\.text\s*==\s*([rRuU]?[\'"])(.*?)\1', skills_src, flags=re.S)
if m:
    dump("expected_from_test_skills", m.group(2))
else:
    print("Did not find echo expected literal in tests/test_skills.py")

# tests/test_router.py — find: ('Hello' in resp.text) and '...' in resp.text
router_src = pathlib.Path("tests/test_router.py").read_text(encoding="utf-8")
m = re.search(r"\('Hello'\s+in\s+resp\.text\)\s+and\s*([rRuU]?[\'\"])(.*?)\1\s+in\s+resp\.text", router_src, flags=re.S)
if m:
    dump("substring_from_test_router", m.group(2))
else:
    print("Did not find router substring in tests/test_router.py")