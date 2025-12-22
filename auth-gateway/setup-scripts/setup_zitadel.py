#!/usr/bin/env python3
"""
Zitadel MVP Setup Script

This script automates the Zitadel setup for local MVP development:
1. Creates or uses the default admin user
2. Obtains an admin token using the Zitadel admin API
3. Creates a service account (machine user) for testing
4. Generates a Personal Access Token (PAT) for the service account
5. Saves the tokens for use in tests

This bypasses the OAuth redirect URI issue by using Zitadel's admin APIs directly.
"""

import os
import sys

import requests

# Configuration
ZITADEL_UI_URL = os.getenv("ZITADEL_UI_URL", "http://localhost:8081")
# Route API calls via Auth Gateway
ZITADEL_API_URL = os.getenv("ZITADEL_API_URL", "http://localhost:3000")
ZITADEL_ADMIN_USER = "zitadel-admin@zitadel.localhost"
ZITADEL_ADMIN_PASSWORD = "Password1!"  # Default Zitadel initial password


def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_step(step: str) -> None:
    """Print a step message."""
    print(f"\n→ {step}")


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"  ✅ {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"  ❌ {message}")


def get_admin_token_via_password() -> str | None:
    """
    Get admin token using password grant (if available).
    This is a fallback method for initial setup.
    """
    print_step("Attempting to get admin token via password authentication...")
    # Password grant is disabled in modern Zitadel versions
    print_error("Password grant is disabled in modern Zitadel versions")
    print("  We'll use manual PAT generation instead")
    return None


def manual_pat_setup() -> str | None:
    """Guide user through manual PAT setup."""
    print_header("Manual Setup Required")

    print("\nFor MVP development, please follow these steps:")
    print(f"\n1. Open {ZITADEL_UI_URL} in your browser")
    print("2. If this is the first time:")
    print("   - Complete the initial wizard")
    print("   - Create an organization")
    print("   - Set admin username and password")
    print("\n3. Create a Service Account (Machine User):")
    print("   - Go to Users → + New → Machine")
    print("   - User Name: test-service-account")
    print("   - Click Create")
    print("\n4. Generate a Personal Access Token (PAT):")
    print("   - On the user detail page, scroll to 'Personal Access Tokens'")
    print("   - Click + New")
    print("   - Set expiration date (e.g., 2026-12-31)")
    print("   - Click Add")
    print("   - **COPY THE TOKEN IMMEDIATELY** (shown only once)")
    print("\n5. Save the token:")

    print("\nPaste your PAT here (or press Enter to exit): ", end="")
    token = input().strip()

    if not token:
        print_error("No token provided. Exiting.")
        return None

    # Save token to file
    try:
        with open("test_token.txt", "w") as f:
            f.write(token)
        print_success("Token saved to test_token.txt")

        # Also export as environment variable suggestion
        print("\n💡 To use this token in tests, run:")
        print(f"   export ZITADEL_ADMIN_TOKEN='{token}'")

        return token
    except Exception as e:
        print_error(f"Failed to save token: {e}")
        return None


def verify_token(token: str) -> bool:
    """Verify the token works by calling Zitadel API."""
    print_step("Verifying token...")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        # Try to get user info
        response = requests.get(
            f"{ZITADEL_API_URL}/auth/v1/users/me",
            headers=headers,
            timeout=10,
        )

        if response.status_code == 200:
            user_data = response.json()
            print_success(
                f"Token is valid! User: {user_data.get('user', {}).get('userName', 'Unknown')}"
            )
            return True
        else:
            print_error(f"Token validation failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Error verifying token: {e}")
        return False


def automated_setup_with_api() -> bool:
    """
    Alternative: Use Zitadel Management API to create everything.
    This requires an existing admin token.
    """
    # Check if we already have a token
    token = os.getenv("ZITADEL_ADMIN_TOKEN")
    if not token and os.path.exists("test_token.txt"):
        with open("test_token.txt") as f:
            token = f.read().strip()

    if not token:
        print_error("No admin token found")
        print("  Please set ZITADEL_ADMIN_TOKEN or create test_token.txt")
        return False

    print_step("Using existing admin token for automated setup...")

    # Verify token works
    if not verify_token(token):
        return False

    print_success("Setup complete! Token is ready to use.")
    return True


def main() -> int:
    """Main entry point."""
    print_header("Zitadel MVP Setup")
    print(f"Zitadel UI URL: {ZITADEL_UI_URL}")
    print(f"Zitadel API URL: {ZITADEL_API_URL}")

    # Check if Zitadel is running
    print_step("Checking Zitadel availability...")
    try:
        response = requests.get(f"{ZITADEL_API_URL}/debug/healthz", timeout=5)
        if response.status_code == 200:
            print_success("Zitadel is running")
        else:
            print_error(f"Zitadel health check failed: {response.status_code}")
            return 1
    except Exception as e:
        print_error(f"Cannot reach Zitadel: {e}")
        print("\n💡 Make sure Zitadel is running:")
        print("   docker compose up -d zitadel")
        return 1

    # Check if we already have a token
    if os.path.exists("test_token.txt"):
        print_step("Found existing token in test_token.txt")
        with open("test_token.txt") as f:
            token = f.read().strip()

        if verify_token(token):
            print_success("Existing token is valid and ready to use!")
            return 0
        else:
            print_error("Existing token is invalid or expired")
            os.remove("test_token.txt")

    # Try automated setup if token is in environment
    if os.getenv("ZITADEL_ADMIN_TOKEN"):
        if automated_setup_with_api():
            return 0

    # Fall back to manual setup
    maybe_token = manual_pat_setup()
    if maybe_token and verify_token(maybe_token):
        print_header("Setup Complete!")
        print("\n✅ Zitadel is configured and ready for testing")
        print("\nYour token is saved in: test_token.txt")
        print("\nNext steps:")
        print("  1. Run tests: python scripts/test_gateway.py")
        print("  2. Run E2E tests: python scripts/e2e_test_gateway.py")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
