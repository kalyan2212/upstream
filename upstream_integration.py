"""
upstream_integration.py
=======================
Example: How the UPSTREAM application pushes customer records
INTO the data-entry application via its REST API.

Usage:
    python upstream_integration.py

Requirements:
    pip install requests
"""

import requests

# ─── Configuration ────────────────────────────────────────────────────────────
BASE_URL = "http://localhost:5000"
API_KEY  = "upstream-app-key-001"   # must match an entry in app.py API_KEYS

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
}
# ──────────────────────────────────────────────────────────────────────────────


def push_customer(customer: dict) -> dict:
    """
    Send one customer record to the data-entry app.
    Returns the created record (with its new id and created_at) on success.
    Raises RuntimeError on failure.
    """
    response = requests.post(
        f"{BASE_URL}/api/customers",
        json=customer,
        headers=HEADERS,
        timeout=10,
    )

    if response.status_code == 201:
        created = response.json()
        print(f"[OK] Customer created  id={created['id']}  "
              f"name={created['first_name']} {created['last_name']}")
        return created

    # validation errors (422) or server errors
    print(f"[FAIL] HTTP {response.status_code}: {response.text}")
    raise RuntimeError(f"Failed to push customer: {response.text}")


def push_batch(customers: list[dict]) -> list[dict]:
    """Push a list of customer records one by one and return all created records."""
    created = []
    for i, customer in enumerate(customers, start=1):
        print(f"Pushing record {i}/{len(customers)} ...")
        try:
            created.append(push_customer(customer))
        except RuntimeError as exc:
            print(f"  Skipping record {i}: {exc}")
    print(f"\nDone. {len(created)}/{len(customers)} records pushed successfully.")
    return created


# ─── Demo ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_customers = [
        {
            "first_name": "Alice",
            "last_name":  "Johnson",
            "road":       "10 Elm Street",
            "city":       "Boston",
            "state":      "MA",
            "zip":        "02101",
            "country":    "USA",
            "phone":      "6171234567",
            "dob":        "03/15/1985",
        },
        {
            "first_name": "Bob",
            "last_name":  "Williams",
            "road":       "55 Oak Avenue",
            "city":       "Chicago",
            "state":      "IL",
            "zip":        "60601",
            "country":    "USA",
            "phone":      "3129876543",
            "dob":        "07/22/1990",
        },
        {
            # Intentionally bad record to show error handling
            "first_name": "Charlie",
            "last_name":  "Brown",
            "road":       "",          # missing – will trigger 422
            "city":       "New York",
            "state":      "NY",
            "zip":        "10001",
            "country":    "USA",
            "phone":      "2125550001",
            "dob":        "11/30/1978",
        },
    ]

    push_batch(sample_customers)
