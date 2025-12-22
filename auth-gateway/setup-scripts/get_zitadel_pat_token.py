#!/usr/bin/env python3
"""
Generate a Personal Access Token (PAT) for a Zitadel Service User.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from typing import Any

import requests  # type: ignore

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:3000")


def create_pat(
    base_url: str, admin_token: str, user_id: str, expiration_days: int = 365
) -> str | None:
    """Create PAT for user (e.g., service account)"""
    url = f"{base_url}/management/v1/users/{user_id}/pats"

    expiration = (datetime.utcnow() + timedelta(days=expiration_days)).isoformat() + "Z"

    payload = {
        "expiration_date": expiration,
        "access_token_type": 1,  # BEARER
    }

    print(f"🔧 Creating PAT for user {user_id}...")
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            token: str = data["token"]
            print("✅ PAT Created Successfully!")
            return token
        else:
            print(f"❌ Failed to create PAT: {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Zitadel PAT for a Service User")
    parser.add_argument(
        "--admin-token-file", required=True, help="Path to file containing Zitadel Admin Token"
    )
    parser.add_argument(
        "--user-id", required=True, help="ID of the Service User to generate PAT for"
    )
    parser.add_argument(
        "--url", default=GATEWAY_URL, help=f"Zitadel/Gateway URL (default: {GATEWAY_URL})"
    )

    args = parser.parse_args()

    if not os.path.exists(args.admin_token_file):
        print(f"❌ Admin token file not found: {args.admin_token_file}")
        sys.exit(1)

    with open(args.admin_token_file, "r") as f:
        admin_token = f.read().strip()

    token = create_pat(args.url, admin_token, args.user_id)

    if token:
        print("\n" + "=" * 60)
        print("YOUR PAT TOKEN:")
        print("=" * 60)
        print(token)
        print("=" * 60)

        # Also save to file
        outfile = f"pat_token_{args.user_id}.txt"
        with open(outfile, "w") as f:
            f.write(token)
        print(f"\nSaved to {outfile}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
