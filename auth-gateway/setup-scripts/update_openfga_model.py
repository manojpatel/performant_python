#!/usr/bin/env python3
"""
Upload updated OpenFGA authorization model from file.
Validates model compatibility against provided tests before uploading.
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

OPENFGA_URL = "http://localhost:8889"
STORE_ID = "01KCYQYGFWDDHRXTNW1VMNX5AW"


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


def upload_model(model: dict[str, Any]) -> dict[str, Any]:
    """Upload model to OpenFGA"""
    url = f"{OPENFGA_URL}/stores/{STORE_ID}/authorization-models"

    print("\n📤 Uploading model to OpenFGA...")
    print(f"   URL: {url}")

    response = requests.post(url, json=model, timeout=10)

    if response.status_code in [200, 201]:
        data: dict[str, Any] = response.json()
        print("✅ Model uploaded successfully!")
        print(f"   Authorization Model ID: {data.get('authorization_model_id')}")
        return data
    else:
        print(f"❌ Failed to upload model: {response.status_code}")
        print(f"   Response: {response.text}")
        sys.exit(1)


def verify_model() -> None:
    """Verify the model was uploaded"""
    url = f"{OPENFGA_URL}/stores/{STORE_ID}/authorization-models"

    response = requests.get(url, timeout=10)

    if response.status_code == 200:
        data = response.json()
        models = data.get("authorization_models", [])
        print(f"\n📋 Total models in store: {len(models)}")
        if models:
            latest = models[0]
            print(f"   Latest model ID: {latest.get('id')}")
    else:
        print(f"⚠️  Could not verify models: {response.status_code}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update OpenFGA model from file with compatibility checks"
    )
    parser.add_argument("--model", required=True, help="Path to new model file (.fga or .json)")
    parser.add_argument("--tests", required=True, help="Path to .fga.yaml test definition file")
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"❌ Model file not found: {args.model}")
        sys.exit(1)

    if not os.path.exists(args.tests):
        print(f"❌ Test file not found: {args.tests}")
        sys.exit(1)

    print("=" * 70)
    print("OPENFGA MODEL UPDATE - File Based Migration")
    print("=" * 70)
    print(f"Model: {args.model}")
    print(f"Tests: {args.tests}")
    print()

    # 1. Validation
    print("1️⃣ Verifying compatibility...")
    if not run_model_tests(args.model, args.tests):
        print("\n❌ ABORTING: New model failed compatibility tests.")
        sys.exit(1)

    # 2. Load/Transform Model
    print("\n2️⃣ Preparing model for upload...")
    model_json = load_model(args.model)

    # 3. Upload
    print("\n3️⃣ Uploading to OpenFGA...")
    upload_model(model_json)

    # 4. Verify
    print("\n4️⃣ Verifying upload...")
    verify_model()

    print("\n" + "=" * 70)
    print("✅ Model update complete!")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
