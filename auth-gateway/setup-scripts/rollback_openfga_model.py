#!/usr/bin/env python3
"""
Rollback OpenFGA authorization model.
Lists previous models, fetches the definition of a selected one,
and re-uploads it as the new latest model.
"""

import argparse
import sys
from datetime import datetime
from typing import Any, cast  # noqa: UP035

import requests

OPENFGA_URL = "http://localhost:8889"
STORE_ID = "01KCYQYGFWDDHRXTNW1VMNX5AW"


def list_models() -> list[dict[str, Any]]:
    """List all authorization models for the store."""
    url = f"{OPENFGA_URL}/stores/{STORE_ID}/authorization-models"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return cast(list[dict[str, Any]], data.get("authorization_models", []))
    except requests.RequestException as e:
        print(f"❌ Failed to list models: {e}")
        sys.exit(1)


def get_model(model_id: str) -> dict[str, Any]:
    """Fetch the full definition of a specific model."""
    url = f"{OPENFGA_URL}/stores/{STORE_ID}/authorization-models/{model_id}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return cast(dict[str, Any], response.json())
    except requests.RequestException as e:
        print(f"❌ Failed to fetch model {model_id}: {e}")
        sys.exit(1)


def upload_model(model_def: dict[str, Any]) -> str:
    """Upload a model definition as a new authorization model."""
    url = f"{OPENFGA_URL}/stores/{STORE_ID}/authorization-models"

    # We need to extract just the type_definitions and schema_version
    # The get_model response might wrap them or include ID/dates which we don't send back
    payload = {
        "type_definitions": model_def.get("type_definitions", []),
        "schema_version": model_def.get("schema_version", "1.1"),
    }

    # If the model has 'conditions' (OpenFGA 1.1+), include them
    if "conditions" in model_def:
        payload["conditions"] = model_def["conditions"]

    print("📤 Uploading rollback model...")
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code not in [200, 201]:
            print(f"❌ Failed to upload model: {response.text}")
            sys.exit(1)

        data = response.json()
        new_id = data.get("authorization_model_id")
        print(f"✅ Rollback successful! New Model ID: {new_id}")
        return str(new_id)
    except requests.RequestException as e:
        print(f"❌ Network error during upload: {e}")
        sys.exit(1)


def format_date(iso_date: str) -> str:
    try:
        # OpenFGA returns RFC3339-like strings
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return iso_date


def main() -> None:
    parser = argparse.ArgumentParser(description="Rollback OpenFGA Authorization Model")
    parser.add_argument("--id", help="Directly specify the Model ID to rollback to")
    args = parser.parse_args()

    print(f"Connecting to OpenFGA at {OPENFGA_URL} (Store: {STORE_ID})\n")

    if args.id:
        target_id = args.id
        print(f"Targeting specific Model ID: {target_id}")
    else:
        # Interactive mode
        models = list_models()
        if not models:
            print("No authorization models found.")
            sys.exit(0)

        print(f"{'INDEX':<6} {'MODEL ID':<28} {'CREATED AT':<25}")
        print("-" * 60)

        for idx, m in enumerate(models):
            created = format_date(m.get("uploaded_at", "N/A"))
            m_id = m.get("id", "UNKNOWN")
            # Mark the current latest
            is_latest = " (LATEST)" if idx == 0 else ""
            print(f"[{idx}]    {m_id}   {created}{is_latest}")

        print("-" * 60)

        while True:
            selection = input("\nEnter index of model to restore (or 'q' to quit): ").strip()
            if selection.lower() == "q":
                sys.exit(0)

            try:
                idx = int(selection)
                if 0 <= idx < len(models):
                    target_id = models[idx]["id"]
                    break
                else:
                    print("Invalid index.")
            except ValueError:
                print("Please enter a number.")

    print(f"\n🔄 Rolling back to model version: {target_id}")

    # 1. Fetch the target model definition
    full_model = get_model(target_id)

    # 2. Re-upload it as new
    new_id = upload_model(full_model)

    print(
        f"\n🎉 Rollback Complete. The application will now use"
        f"version {new_id} (which is a clone of {target_id})."
    )


if __name__ == "__main__":
    main()
