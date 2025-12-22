import json
import os
import sys
import time
import uuid

import jwt
import requests

# Configuration
ZITADEL_ISSUER = "http://127.0.0.1.nip.io:8081"
GATEWAY_URL = "http://localhost:3000"
TOKEN_ENDPOINT = f"{GATEWAY_URL}/oauth/v2/token"
SCOPES = "openid profile email urn:zitadel:iam:org:project:id:zitadel:aud"


def get_access_token(key_file_path: str) -> str:
    with open(key_file_path) as f:
        key_data = json.load(f)

    user_id = key_data["userId"]
    key_id = key_data["keyId"]
    private_key = key_data["key"]

    now = int(time.time())
    payload = {
        "iss": user_id,
        "sub": user_id,
        "aud": ZITADEL_ISSUER,
        "exp": now + 3600,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }

    headers = {"kid": key_id, "alg": "RS256"}

    # Sign the JWT with the private key
    encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256", headers=headers)

    # Exchange for Access Token
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": encoded_jwt,
        "scope": SCOPES,
    }

    try:
        response = requests.post(TOKEN_ENDPOINT, data=data)
        response.raise_for_status()
        token_data = response.json()
        access_token = str(token_data.get("access_token", ""))
        id_token = str(token_data.get("id_token", ""))

        if access_token:
            print(f"Using Access Token (Length: {len(access_token)})")
            return access_token

        if id_token:
            print("Using ID Token (JWT) as fallback (Note: API calls might reject this).")
            return id_token

        return access_token
    except requests.exceptions.HTTPError as e:
        print(f"Error getting token: {e}")
        print(f"Response: {response.text}")
        sys.exit(1)


if __name__ == "__main__":
    if not os.path.exists("zitadel-key.json"):
        print("Error: 'zitadel-key.json' not found.")
        print(
            "Please place the downloaded JSON key file in the current directory and "
            "rename it to 'zitadel-key.json'."
        )
        sys.exit(1)

    token = get_access_token("zitadel-key.json")
    print("Successfully obtained Access Token!")

    # Save to file for test_gateway.py
    with open("test_token.txt", "w") as f:
        f.write(token)
    print("Token saved to 'test_token.txt'. You can now run 'python3 scripts/test_gateway.py'.")
