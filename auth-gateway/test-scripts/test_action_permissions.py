#!/usr/bin/env python3
"""
Test action-based authorization with hierarchical permissions.
Verifies that admin, manager, and viewer roles have appropriate access.
"""

import requests

OPENFGA_URL = "http://localhost:8889"
STORE_ID = "01KCYQYGFWDDHRXTNW1VMNX5AW"


def create_test_permissions() -> bool:
    """
    Create test users with different roles:
    - test_admin: admin role (can view, edit, delete)
    - test_manager: manager role (can view, edit, no delete)
    - test_viewer: viewer role (can only view)
    """
    url = f"{OPENFGA_URL}/stores/{STORE_ID}/write"

    tuples = [
        # Admin user
        {"user": "user:test_admin", "relation": "admin", "object": "feature:reporting"},
        # Manager user
        {"user": "user:test_manager", "relation": "manager", "object": "feature:reporting"},
        # Viewer user
        {"user": "user:test_viewer", "relation": "viewer", "object": "feature:reporting"},
    ]

    payload = {"writes": {"tuple_keys": tuples}}

    print("📝 Creating test permissions...")
    response = requests.post(url, json=payload, timeout=10)

    if response.status_code == 200:
        print("✅ Test permissions created")
        return True
    else:
        print(f"❌ Failed to create permissions: {response.status_code}")
        print(f"   Response: {response.text}")
        return False


def check_permission(user_id: str, action: str) -> bool:
    """Check if user has permission for action on reporting feature"""
    url = f"{OPENFGA_URL}/stores/{STORE_ID}/check"

    payload = {
        "tuple_key": {"user": f"user:{user_id}", "relation": action, "object": "feature:reporting"}
    }

    response = requests.post(url, json=payload, timeout=10)

    if response.status_code == 200:
        result = response.json()
        return bool(result.get("allowed", False))
    else:
        print(f"❌ Check failed: {response.status_code}")
        return False


def test_actions() -> bool:
    """Test all combinations of users and actions"""
    users = ["test_admin", "test_manager", "test_viewer"]
    actions = ["view", "edit", "delete"]

    # Expected results
    expected = {
        ("test_admin", "view"): True,
        ("test_admin", "edit"): True,
        ("test_admin", "delete"): True,
        ("test_manager", "view"): True,
        ("test_manager", "edit"): True,
        ("test_manager", "delete"): False,
        ("test_viewer", "view"): True,
        ("test_viewer", "edit"): False,
        ("test_viewer", "delete"): False,
    }

    print("\n" + "=" * 70)
    print("TESTING ACTION-BASED PERMISSIONS")
    print("=" * 70)
    print()

    results = []

    for user in users:
        print(f"🧪 Testing user: {user}")
        for action in actions:
            allowed = check_permission(user, action)
            exp = expected.get((user, action), False)

            icon = "✅" if allowed == exp else "❌"
            status = "PASS" if allowed == exp else "FAIL"

            print(f"   {icon} {action:6} → {allowed:5} (expected {exp:5}) [{status}]")

            results.append(
                {
                    "user": user,
                    "action": action,
                    "allowed": allowed,
                    "expected": exp,
                    "passed": allowed == exp,
                }
            )
        print()

    # Summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print("=" * 70)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("=" * 70)

    if passed == total:
        print("\n🎉 All tests passed! Hierarchical permissions working correctly!")
        return True
    else:
        print(f"\n❌ {total - passed} tests failed")
        for r in results:
            if not r["passed"]:
                print(
                    f"   - {r['user']} {r['action']}: got {r['allowed']}, expected {r['expected']}"
                )
        return False


def main() -> None:
    print("=" * 70)
    print("ACTION-BASED AUTHORIZATION TEST")
    print("=" * 70)
    print()

    # Create permissions
    if not create_test_permissions():
        return

    # Test permissions
    success = test_actions()

    if success:
        print("\n✅ Implementation verified!")
    else:
        print("\n❌ Issues detected")


if __name__ == "__main__":
    main()
