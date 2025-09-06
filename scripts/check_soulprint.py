from samos.core.soulprint import load_soulprint, DEFAULT_SOULPRINT_PATH

def main():
    sp = load_soulprint()
    print("Soulprint path:", DEFAULT_SOULPRINT_PATH)
    print("Loaded type:", type(sp).__name__)
    if isinstance(sp, dict):
        print("Keys count:", len(sp))
        print("Sample keys:", list(sp.keys())[:5])

if __name__ == "__main__":
    main()
