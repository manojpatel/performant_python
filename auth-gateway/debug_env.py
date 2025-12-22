import sys

print("--- sys.path ---")
for p in sys.path:
    print(p)

try:
    import jwt

    print("\n--- jwt module ---")
    print(f"File: {jwt.__file__}")
    print(f"Dir: {dir(jwt)}")
except ImportError as e:
    print(f"\nError importing jwt: {e}")

try:
    import importlib.metadata

    print("\n--- Installed Packages (importlib.metadata) ---")
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        if "jwt" in name.lower():
            print(f"{name} ({dist.version})")
except ImportError:
    print("\nimportlib.metadata not found (should not happen on Py3.11+)")
