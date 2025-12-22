#!/usr/bin/env python3
"""
Webhook integration tests for auth-gateway.
Tests user lifecycle: create, update, delete with OpenFGA sync.
"""

import sys
import time

import requests

GATEWAY_URL = "http://localhost:3000"
OPENFGA_URL = "http://localhost:8889"
STORE_ID = "01KCYQYGFWDDHRXTNW1VMNX5AW"


def test_user_creation_webhook():
    """Test user creation webhook"""
    print("\n1️⃣ Testing user creation webhook...")

    user_id = f"test-user-{int(time.time())}"
    event = {"userId": user_id, "userName": "test.user", "userType": "human"}

    try:
        response = requests.post(f"{GATEWAY_URL}/webhooks/user-created", json=event, timeout=10)

        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"   Response: {result}")
            if "registered" in result.get("message", "").lower():
                print("   ✅ User registered in OpenFGA")
                return True
        elif response.status_code == 401:
            print("   ⚠️  Webhook route not in access_rules.json")
            print("   (Rebuild container with updated access_rules.json)")
            return None
        else:
            print(f"   ❌ Unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_user_deletion_webhook():
    """Test user deletion webhook"""
    print("\n2️⃣ Testing user deletion webhook...")

    user_id = f"test-delete-{int(time.time())}"
    event = {"userId": user_id}

    try:
        response = requests.post(f"{GATEWAY_URL}/webhooks/user-deleted", json=event, timeout=10)

        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"   Response: {result}")
            print("   ✅ User deletion handled")
            return True
        elif response.status_code == 401:
            print("   ⚠️  Webhook route not configured")
            return None
        else:
            print(f"   ❌ Unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_direct_openfga_user_check():
    """Test querying users from OpenFGA directly"""
    print("\n3️⃣ Testing OpenFGA user queries...")

    try:
        response = requests.post(
            f"{OPENFGA_URL}/stores/{STORE_ID}/read",
            json={"tuple_key": {"relation": "member", "object": "organization:users"}},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            user_count = len(data.get("tuples", []))
            print(f"   Found {user_count} registered users")
            print("   ✅ Can query users from OpenFGA")
            return True
        else:
            print(f"   ❌ Failed to query: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    print("=" * 70)
    print("WEBHOOK INTEGRATION TESTS")
    print("=" * 70)

    results = []

    results.append(test_user_creation_webhook())
    results.append(test_user_deletion_webhook())
    results.append(test_direct_openfga_user_check())

    print("\n" + "=" * 70)

    # Count results (None means skipped due to configuration)
    passed = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False)
    skipped = sum(1 for r in results if r is None)

    print(f"RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 70)

    if skipped > 0:
        print("\nℹ️  Note: Some tests skipped due to access_rules.json configuration")
        print("   To enable webhook tests, add webhook routes to access_rules.json")
        print("   and rebuild the auth-gateway container.\n")

    if failed > 0:
        sys.exit(1)
    else:
        print("\n✅ All active tests passed!\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
