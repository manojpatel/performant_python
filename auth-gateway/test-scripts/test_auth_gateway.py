#!/usr/bin/env python3
"""
Comprehensive test suite for auth-gateway functionality.
Tests: routing, OpenFGA integration, auth middleware, error handling.
"""

import sys

import requests

GATEWAY_URL = "http://localhost:3000"
OPENFGA_URL = "http://localhost:8889"
STORE_ID = "01KCYQYGFWDDHRXTNW1VMNX5AW"


class TestResult:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.errors: list[tuple[str, str]] = []

    def add_pass(self, test_name: str) -> None:
        self.passed += 1
        print(f"   ✅ {test_name}")

    def add_fail(self, test_name: str, error: str) -> None:
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"   ❌ {test_name}: {error}")

    def summary(self) -> bool:
        print("\n" + "=" * 70)
        print(f"RESULTS: {self.passed} passed, {self.failed} failed")
        print("=" * 70)
        if self.errors:
            print("\nFailed Tests:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")
        return self.failed == 0


def test_gateway_health(results: TestResult) -> None:
    """Test basic gateway connectivity"""
    print("\n1️⃣ Gateway Health Checks")
    try:
        response = requests.get(f"{GATEWAY_URL}/api/health", timeout=5)
        if response.status_code in [401, 403, 404]:
            results.add_pass("Gateway responds")
        else:
            results.add_fail("Gateway responds", f"Unexpected status {response.status_code}")
    except Exception as e:
        results.add_fail("Gateway responds", str(e))


def test_openfga_routing(results: TestResult) -> None:
    """Test OpenFGA multi-backend routing"""
    print("\n2️⃣ OpenFGA Routing Tests")

    # Test store access via gateway
    try:
        response = requests.get(f"{GATEWAY_URL}/stores/{STORE_ID}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("id") == STORE_ID:
                results.add_pass("Route to OpenFGA store")
            else:
                results.add_fail("Route to OpenFGA store", "Wrong store ID")
        else:
            results.add_fail("Route to OpenFGA store", f"Status {response.status_code}")
    except Exception as e:
        results.add_fail("Route to OpenFGA store", str(e))

    # Test direct OpenFGA
    try:
        response = requests.get(f"{OPENFGA_URL}/stores", timeout=5)
        if response.status_code == 200:
            results.add_pass("Direct OpenFGA access")
        else:
            results.add_fail("Direct OpenFGA access", f"Status {response.status_code}")
    except Exception as e:
        results.add_fail("Direct OpenFGA access", str(e))


def test_auth_middleware(results: TestResult) -> None:
    """Test authentication and authorization"""
    print("\n3️⃣ Auth Middleware Tests")

    # Test unauthorized access blocked
    try:
        response = requests.get(f"{GATEWAY_URL}/api/data", timeout=5)
        if response.status_code == 401:
            results.add_pass("Blocks unauthorized requests")
        else:
            results.add_fail("Blocks unauthorized requests", f"Status {response.status_code}")
    except Exception as e:
        results.add_fail("Blocks unauthorized requests", str(e))

    # Test missing auth header
    try:
        response = requests.get(f"{GATEWAY_URL}/api/test", timeout=5)
        if response.status_code in [401, 403]:
            results.add_pass("Requires auth header")
        else:
            results.add_fail("Requires auth header", f"Status {response.status_code}")
    except Exception as e:
        results.add_fail("Requires auth header", str(e))


def test_error_handling(results: TestResult) -> None:
    """Test graceful error handling"""
    print("\n4️⃣ Error Handling Tests")

    # Test invalid route
    try:
        response = requests.get(f"{GATEWAY_URL}/nonexistent/route", timeout=5)
        # Auth middleware runs first, so 401 is expected for unauthed requests
        if response.status_code in [401, 403, 404]:
            results.add_pass("Handles invalid routes")
        else:
            results.add_fail("Handles invalid routes", f"Status {response.status_code}")
    except Exception as e:
        results.add_fail("Handles invalid routes", str(e))

    # Test OpenFGA error recovery
    try:
        response = requests.get(f"{GATEWAY_URL}/stores/invalid-id", timeout=5)
        # Gateway should handle this gracefully (either 400 or proxy the error)
        if response.status_code in [400, 404, 500]:
            results.add_pass("Handles OpenFGA errors")
        else:
            results.add_fail("Handles OpenFGA errors", f"Status {response.status_code}")
    except Exception as e:
        results.add_fail("Handles OpenFGA errors", str(e))


def main() -> None:
    print("=" * 70)
    print("AUTH-GATEWAY TEST SUITE")
    print("=" * 70)

    results = TestResult()

    test_gateway_health(results)
    test_openfga_routing(results)
    test_auth_middleware(results)
    test_error_handling(results)

    success = results.summary()

    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
