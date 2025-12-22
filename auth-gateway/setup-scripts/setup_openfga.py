#!/usr/bin/env python3
"""
Bootstrap OpenFGA Store and Model with mandatory safety checks.
"""

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from typing import Any

import requests
import yaml  # type: ignore

# Use Auth Gateway port 3000 (default), or override for bootstrap
OPENFGA_API_URL = os.getenv("OPENFGA_API_URL", "http://localhost:3000")


def ensure_fga_cli() -> str:
    """Ensure fga CLI is available, download if necessary."""
    # Check if fga is in path
    if os.system("which fga > /dev/null 2>&1") == 0:
        return "fga"

    # Check local tmp dir
    tmp_dir = os.path.join(tempfile.gettempdir(), "fga_cli")
    fga_path = os.path.join(tmp_dir, "fga")

    if os.path.exists(fga_path):
        return fga_path

    print("⚠️  'fga' CLI not found. Downloading...")
    os.makedirs(tmp_dir, exist_ok=True)

    # Download URL for Linux amd64
    url = "https://github.com/openfga/cli/releases/download/v0.6.3/fga_0.6.3_linux_amd64.tar.gz"
    response = requests.get(url, stream=True)

    if response.status_code == 200:
        tar_path = os.path.join(tmp_dir, "fga.tar.gz")
        with open(tar_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Extract
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(path=tmp_dir)

        # Make executable
        st = os.stat(fga_path)
        os.chmod(fga_path, st.st_mode | stat.S_IEXEC)
        print(f"✅ Downloaded fga CLI to {fga_path}")
        return fga_path
    else:
        print(f"❌ Failed to download fga CLI: {response.status_code}")
        sys.exit(1)


def run_model_tests(model_path: str, original_tests_path: str) -> bool:
    """Run OpenFGA tests against the provided model file."""
    fga_bin = ensure_fga_cli()

    # Create a temporary directory to isolate test execution
    with tempfile.TemporaryDirectory() as tmp_dir:
        # 1. Copy model file to temp dir
        model_filename = os.path.basename(model_path)
        tmp_model_path = os.path.join(tmp_dir, model_filename)
        shutil.copy2(model_path, tmp_model_path)

        # 2. Setup test file path in temp dir
        tests_filename = "tests.fga.yaml"
        tmp_tests_path = os.path.join(tmp_dir, tests_filename)

        # 3. Read original test config
        try:
            with open(original_tests_path) as f:
                test_config = yaml.safe_load(f)
        except Exception as e:
            print(f"❌ Failed to read test file: {e}")
            return False

        # 4. Update model_file logic
        # If the original test config had a model_file, we override it to point
        # to the local copy in the same directory.
        test_config["model_file"] = f"./{model_filename}"

        # 5. Write the modified test config to temp dir
        with open(tmp_tests_path, "w") as f:
            yaml.dump(test_config, f)

        print(f"\n🧪 Running tests using model copy at: {tmp_model_path}...")
        try:
            # Run fga model test --tests <tmp_tests_path>
            # Since everything is in tmp_dir, relative paths inside yaml work.
            cmd = [fga_bin, "model", "test", "--tests", tmp_tests_path]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print("✅ Compatibility Verify: All tests passed!")
                return True
            else:
                print("❌ Compatibility Verify: Tests FAILED")
                print(result.stdout)
                print(result.stderr)
                return False
        except Exception as e:
            print(f"❌ Execution error: {e}")
            return False


def transform_dsl_to_json(dsl_path: str) -> dict[str, Any]:
    """Transform .fga DSL file to JSON using fga CLI."""
    fga_bin = ensure_fga_cli()
    print(f"\n🔄 Transforming DSL to JSON: {dsl_path}")

    cmd = [fga_bin, "model", "transform", "--file", dsl_path]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("❌ Failed to transform model DSL to JSON")
        print(result.stderr)
        sys.exit(1)

    try:
        return dict(json.loads(result.stdout))
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse transformed JSON: {e}")
        print(result.stdout)
        sys.exit(1)


def load_model(model_path: str) -> dict[str, Any]:
    """Load model from file, converting DSL to JSON if needed."""
    if model_path.endswith(".json"):
        with open(model_path) as f:
            return dict(json.load(f))
    else:
        # Assume DSL (.fga)
        return transform_dsl_to_json(model_path)


def get_headers() -> dict[str, str]:
    if not os.path.exists("test_token.txt"):
        print("Warning: test_token.txt not found. Requests through gateway may fail.")
        return {}
    with open("test_token.txt") as f:
        token = f.read().strip()
    return {"Authorization": f"Bearer {token}"}


def create_store() -> str:
    print(f"Creating OpenFGA Store at {OPENFGA_API_URL}...")
    headers = get_headers()
    try:
        response = requests.post(
            f"{OPENFGA_API_URL}/stores", json={"name": "performant-python-store"}, headers=headers
        )
        response.raise_for_status()
        data = response.json()
        store_id: str = data["id"]
        print(f"✅ Store created: {store_id}")
        return store_id
    except Exception as e:
        print(f"❌ Failed to create store: {e}")
        if "response" in locals():
            print(f"Response: {response.text}")
        sys.exit(1)


def create_model(store_id: str, model_path: str) -> str:
    print("Creating Authorization Model...")
    headers = get_headers()

    model_json = load_model(model_path)

    try:
        response = requests.post(
            f"{OPENFGA_API_URL}/stores/{store_id}/authorization-models",
            json=model_json,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        model_id: str = data["authorization_model_id"]
        print(f"✅ Model created: {model_id}")
        return model_id
    except Exception as e:
        print(f"❌ Failed to create model: {e}")
        if "response" in locals():
            print(response.text)
        sys.exit(1)


def write_tuples(store_id: str, model_id: str, tuples_path: str) -> None:
    print(f"Reading tuples from {tuples_path}...")
    headers = get_headers()

    try:
        with open(tuples_path) as f:
            data = yaml.safe_load(f)
            tuples_list = data.get("tuples", [])
    except Exception as e:
        print(f"❌ Failed to read tuples file: {e}")
        sys.exit(1)

    # Convert YAML format to OpenFGA API format
    tuple_keys = []
    for t in tuples_list:
        tuple_keys.append({"user": t["user"], "relation": t["relation"], "object": t["object"]})

    writes = {
        "writes": {"tuple_keys": tuple_keys},
        "authorization_model_id": model_id,
    }

    try:
        response = requests.post(
            f"{OPENFGA_API_URL}/stores/{store_id}/write", json=writes, headers=headers
        )
        response.raise_for_status()
        print(f"✅ Written {len(tuple_keys)} tuples successfully")
    except Exception as e:
        print(f"❌ Failed to write tuples: {e}")
        if "response" in locals():
            print(response.text)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap OpenFGA Store and Model")
    parser.add_argument("--model", required=True, help="Path to model file (.fga or .json)")
    parser.add_argument("--tests", required=True, help="Path to .fga.yaml test definition file")
    parser.add_argument("--tuples", required=True, help="Path to .yaml tuples seed file")
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"❌ Model file not found: {args.model}")
        sys.exit(1)

    if not os.path.exists(args.tests):
        print(f"❌ Test file not found: {args.tests}")
        sys.exit(1)

    if not os.path.exists(args.tuples):
        print(f"❌ Tuples file not found: {args.tuples}")
        sys.exit(1)

    print("=" * 70)
    print("OPENFGA SETUP - Bootstrap with Safety Checks")
    print("=" * 70)
    print(f"Model: {args.model}")
    print(f"Tests: {args.tests}")
    print(f"Tuples: {args.tuples}")
    print()

    # 1. Validation
    print("1️⃣ Verifying compatibility...")
    if not run_model_tests(args.model, args.tests):
        print("\n❌ ABORTING: Model failed compatibility tests. Store will NOT be created.")
        sys.exit(1)

    # 2. Creation
    print("\n2️⃣ Creating environment...")
    store_id = create_store()
    model_id = create_model(store_id, args.model)

    # 3. Seeding
    print("\n3️⃣ Seeding tuples...")
    write_tuples(store_id, model_id, args.tuples)

    print("\n--- Setup Complete ---")
    print(f"OPENFGA_STORE_ID={store_id}")

    # Write to a file for easy reading
    with open("openfga_store.id", "w") as f:
        f.write(store_id)


if __name__ == "__main__":
    main()
