"""
Razorpay Payment Links integration (test mode).

This module provides a bounded payment-collection rail for SplitSettle AI:

    Settlement
        ↓
    Razorpay Payment Link
        ↓
    Human completes payment on Razorpay
        ↓
    SplitSettle polls Payment Link status
        ↓
    Settlement becomes paid

If RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not set, the application uses
a local mock so the rest of the demo can still run end-to-end.

IMPORTANT:
The mock fallback is clearly distinguishable from a real Razorpay link.
It must never be presented as a real payment.

Razorpay Payment Link statuses supported by the API:
    created
    partially_paid
    paid
    expired
    cancelled
"""

import math
import os
import uuid
from typing import Dict

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Optional Razorpay client
# ---------------------------------------------------------------------------

try:
    import razorpay

    _KEY_ID = os.getenv("RAZORPAY_KEY_ID")
    _KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

    _client = (
        razorpay.Client(
            auth=(_KEY_ID, _KEY_SECRET)
        )
        if _KEY_ID and _KEY_SECRET
        else None
    )

except Exception:
    _client = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MOCK_PREFIX = "plink_mock_"

VALID_STATUSES = {
    "created",
    "partially_paid",
    "paid",
    "expired",
    "cancelled",
}

# Razorpay documents reference_id as having a maximum length of 40.
MAX_REFERENCE_ID_LENGTH = 40

# Razorpay Payment Link description supports a much larger value, but keeping
# our description compact makes the dashboard easier to read.
MAX_DESCRIPTION_LENGTH = 200

MAX_CUSTOMER_NAME_LENGTH = 100


# ---------------------------------------------------------------------------
# Mock payment-link store
# ---------------------------------------------------------------------------

# In-memory store for mock links so get_link_status() can find them.
_mock_links: Dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _amount_to_paise(amount_rupees: float) -> int:
    """
    Convert a rupee amount to paise safely.

    Example:
        ₹420.50 → 42050 paise
    """

    try:
        amount = float(amount_rupees)
    except (TypeError, ValueError):
        raise ValueError("Payment amount must be a valid number.")

    if not math.isfinite(amount):
        raise ValueError("Payment amount must be finite.")

    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    paise = int(round(amount * 100))

    if paise <= 0:
        raise ValueError("Payment amount must be at least ₹0.01.")

    return paise


def _clean_text(value, max_length: int) -> str:
    """Normalize text before sending it to Razorpay."""

    if value is None:
        return ""

    text = " ".join(str(value).split()).strip()

    return text[:max_length]


def _safe_reference_id(reference_id: str) -> str:
    """
    Generate a unique reference ID while staying within Razorpay's
    documented 40-character limit.
    """

    base = _clean_text(
        reference_id,
        MAX_REFERENCE_ID_LENGTH - 7
    )

    suffix = uuid.uuid4().hex[:6]

    result = f"{base}-{suffix}"

    return result[:MAX_REFERENCE_ID_LENGTH]


def _validate_status(status) -> str:
    """Normalize and validate a Razorpay Payment Link status."""

    if not isinstance(status, str):
        return "created"

    status = status.strip().lower()

    if status not in VALID_STATUSES:
        # Do not invent a new status.
        return "created"

    return status


# ---------------------------------------------------------------------------
# Payment Link creation
# ---------------------------------------------------------------------------

def create_payment_link(
    reference_id: str,
    amount_rupees: float,
    description: str,
    customer_name: str,
) -> dict:
    """
    Create a Razorpay Payment Link.

    Returns:

        {
            "id": "...",
            "short_url": "...",
            "status": "created"
        }

    When Razorpay credentials are configured, this creates an actual
    Razorpay test-mode Payment Link.

    Without credentials, it creates a clearly-marked local mock link.
    """

    amount_paise = _amount_to_paise(
        amount_rupees
    )

    clean_description = _clean_text(
        description,
        MAX_DESCRIPTION_LENGTH
    )

    clean_customer_name = _clean_text(
        customer_name,
        MAX_CUSTOMER_NAME_LENGTH
    )

    safe_reference_id = _safe_reference_id(
        reference_id
    )

    # -----------------------------------------------------------------------
    # REAL RAZORPAY PATH
    # -----------------------------------------------------------------------

    if _client:

        payload = {
            # Razorpay expects the smallest currency unit.
            "amount": amount_paise,

            "currency": "INR",

            "description": clean_description,

            # Must be unique and <= 40 characters.
            "reference_id": safe_reference_id,

            "customer": {
                "name": clean_customer_name,
            },

            # SplitSettle owns the reminder workflow, so don't enable
            # Razorpay's independent reminder system for this link.
            "notify": {
                "sms": False,
                "email": False,
            },

            "reminder_enable": False,
        }

        try:
            link = _client.payment_link.create(
                payload
            )

        except Exception as exc:
            raise RuntimeError(
                f"Razorpay Payment Link creation failed: {exc}"
            ) from exc

        link_id = link.get("id")
        short_url = link.get("short_url")
        status = _validate_status(
            link.get("status")
        )

        if not link_id:
            raise RuntimeError(
                "Razorpay returned no Payment Link ID."
            )

        if not short_url:
            raise RuntimeError(
                "Razorpay returned no Payment Link URL."
            )

        return {
            "id": link_id,
            "short_url": short_url,
            "status": status,
        }

    # -----------------------------------------------------------------------
    # MOCK FALLBACK
    # -----------------------------------------------------------------------

    mock_id = (
        f"{MOCK_PREFIX}"
        f"{uuid.uuid4().hex[:10]}"
    )

    _mock_links[mock_id] = {
        "status": "created",
        "amount": round(
            amount_paise / 100,
            2
        ),
        "description": clean_description,
        "customer_name": clean_customer_name,
    }

    return {
        "id": mock_id,
        "short_url": (
            f"https://rzp.io/mock/"
            f"{mock_id[-10:]}"
        ),
        "status": "created",
    }


# ---------------------------------------------------------------------------
# Payment Link status
# ---------------------------------------------------------------------------

def get_link_status(payment_link_id: str) -> str:
    """
    Fetch the current status of a Payment Link.

    Possible statuses:

        created
        partially_paid
        paid
        expired
        cancelled
    """

    if not payment_link_id:
        return "created"

    # -----------------------------------------------------------------------
    # MOCK LINK
    # -----------------------------------------------------------------------

    if payment_link_id.startswith(MOCK_PREFIX):
        return _mock_links.get(
            payment_link_id,
            {}
        ).get(
            "status",
            "created"
        )

    # -----------------------------------------------------------------------
    # REAL RAZORPAY LINK
    # -----------------------------------------------------------------------

    if _client:

        try:
            link = _client.payment_link.fetch(
                payment_link_id
            )

        except Exception as exc:
            raise RuntimeError(
                f"Razorpay Payment Link status check failed: {exc}"
            ) from exc

        return _validate_status(
            link.get("status")
        )

    # -----------------------------------------------------------------------
    # No credentials + unknown non-mock ID
    # -----------------------------------------------------------------------

    # Never pretend an unknown payment link is paid.
    return "created"


# ---------------------------------------------------------------------------
# Integration status
# ---------------------------------------------------------------------------

def is_live() -> bool:
    """
    Returns True when real Razorpay credentials are configured and the
    Razorpay client was successfully initialized.
    """

    return _client is not None