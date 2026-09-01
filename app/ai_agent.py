"""
AI agent layer. Two bounded, explainable capabilities:

1. parse_receipt_text(): turns messy receipt/OCR text into structured line items.
2. generate_reminder(): writes an escalating, personalized nudge for someone
   who owes money on a settlement.

AI is used only for language-heavy tasks. Financial calculations remain
deterministic in the settlement engine.

If ANTHROPIC_API_KEY is not set, both functions fall back to deterministic
rule-based logic so the demo still runs end-to-end without an API key.
"""

import os
import json
import math
import re
from typing import List, Dict


# ---------------------------------------------------------------------------
# Optional Anthropic client
# ---------------------------------------------------------------------------

try:
    import anthropic

    _client = (
        anthropic.Anthropic()
        if os.getenv("ANTHROPIC_API_KEY")
        else None
    )
except Exception:
    _client = None


MODEL = "claude-sonnet-4-6"

# Prevent accidentally sending extremely large pasted receipts to the model.
MAX_RECEIPT_CHARS = 12000

# Keep extracted receipt output bounded and predictable.
MAX_RECEIPT_ITEMS = 100

# Prevent an LLM from producing an absurdly large reminder.
MAX_REMINDER_CHARS = 500


# ---------------------------------------------------------------------------
# Receipt parsing
# ---------------------------------------------------------------------------

def _clean_description(value) -> str:
    """Return a safe, compact receipt-item description."""

    if not isinstance(value, str):
        return ""

    description = " ".join(value.split()).strip()

    # Keep descriptions reasonably sized for the UI/database.
    return description[:200]


def _validate_receipt_items(raw_items) -> List[Dict]:
    """
    Validate and normalize the structure returned by the AI.

    Expected format:
        [
            {"description": "Pizza", "amount": 450.0},
            {"description": "Drinks", "amount": 180.0}
        ]

    Invalid items are discarded rather than allowed to reach the database/UI.
    """

    if not isinstance(raw_items, list):
        return []

    validated = []
    seen = set()

    for item in raw_items[:MAX_RECEIPT_ITEMS]:
        if not isinstance(item, dict):
            continue

        description = _clean_description(
            item.get("description")
        )

        if not description:
            continue

        try:
            amount = float(item.get("amount"))
        except (TypeError, ValueError):
            continue

        # Reject zero, negative, NaN and infinite values.
        if amount <= 0 or not math.isfinite(amount):
            continue

        # Normalize to currency precision.
        amount = round(amount, 2)

        # Avoid duplicate AI output.
        dedupe_key = (
            description.casefold(),
            amount
        )

        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)

        validated.append(
            {
                "description": description,
                "amount": amount,
            }
        )

    return validated


def _extract_json_array(text: str):
    """
    Extract a JSON array from the model response.

    Handles both:
        [...]
    and:
        ```json
        [...]
        ```

    Returns None when the response cannot be parsed.
    """

    if not isinstance(text, str):
        return None

    text = text.strip()

    # Remove Markdown code fences if the model included them.
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    text = text.strip()

    # First try the complete response.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # If the model added extra text, try extracting the first JSON array.
    match = re.search(
        r"\[[\s\S]*\]",
        text
    )

    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def parse_receipt_text(raw_text: str) -> List[Dict]:
    """
    Extract:
        [{"description": str, "amount": float}]

    from OCR output or pasted receipt text.

    Claude is used when an API key is configured. Otherwise, a deterministic
    rule-based parser is used.
    """

    if not isinstance(raw_text, str):
        return []

    raw_text = raw_text.strip()

    if not raw_text:
        return []

    # Prevent excessively large input from reaching the API.
    raw_text = raw_text[:MAX_RECEIPT_CHARS]

    # -----------------------------------------------------------------------
    # AI path
    # -----------------------------------------------------------------------

    if _client:
        prompt = (
            "Extract actual purchased line items from this receipt text.\n\n"
            "Return ONLY a JSON array with this exact structure:\n"
            '[{"description": "Pizza", "amount": 450.00}]\n\n'
            "Rules:\n"
            "1. description must be a short item name.\n"
            "2. amount must be a positive number in INR, without the currency symbol.\n"
            "3. Include actual purchased items only.\n"
            "4. Do not include grand totals, subtotals, tax, GST, discounts, "
            "change, payment-method lines, or receipt metadata.\n"
            "5. Do not invent missing items or amounts.\n"
            "6. Return ONLY the JSON array. No explanation and no Markdown.\n\n"
            f"Receipt text:\n{raw_text}"
        )

        try:
            resp = _client.messages.create(
                model=MODEL,
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            if resp.content:
                text = resp.content[0].text.strip()

                raw_items = _extract_json_array(text)

                validated_items = _validate_receipt_items(
                    raw_items
                )

                if validated_items:
                    return validated_items

        except Exception:
            # Never allow an AI/API failure to break the application.
            pass

    # -----------------------------------------------------------------------
    # Deterministic fallback
    # -----------------------------------------------------------------------

    items = []

    for line in raw_text.splitlines():
        line = line.strip()

        if not line:
            continue

        # Skip obvious total/metadata lines before parsing.
        if re.search(
            r"total|subtotal|tax|gst|change|discount|cash|card|upi|"
            r"invoice|receipt|bill\s*no",
            line,
            re.IGNORECASE
        ):
            continue

        # Look for a positive amount at the end of a line.
        match = re.match(
            r"^(.*?)[\s\-:]*[\u20b9$]?\s*"
            r"([\d,]+(?:\.\d{1,2})?)\s*$",
            line
        )

        if not match:
            continue

        description = _clean_description(
            match.group(1)
        )

        if not description:
            continue

        try:
            amount = float(
                match.group(2).replace(",", "")
            )
        except ValueError:
            continue

        if amount <= 0 or not math.isfinite(amount):
            continue

        items.append(
            {
                "description": description,
                "amount": round(amount, 2),
            }
        )

    return _validate_receipt_items(items)


# ---------------------------------------------------------------------------
# Reminder generation
# ---------------------------------------------------------------------------

REMINDER_TONES = {
    1: (
        "friendly, casual, one-line nudge"
    ),
    2: (
        "polite but a bit more direct, clearly mentions the amount "
        "that is still pending"
    ),
    3: (
        "final firm reminder, still respectful, clearly says this is "
        "the last automated nudge before manual follow-up"
    ),
}


def _fallback_reminder(
    member_name: str,
    amount: float,
    group_name: str,
    level: int
) -> str:
    """Deterministic fallback reminder templates."""

    templates = {
        1: (
            f"Hey {member_name}! Just a heads up, you owe "
            f"₹{amount:.2f} for {group_name}. Whenever you get a chance 🙂"
        ),
        2: (
            f"Hi {member_name}, following up on the ₹{amount:.2f} "
            f"pending for {group_name} — could you settle it soon?"
        ),
        3: (
            f"{member_name}, this is a final reminder: ₹{amount:.2f} "
            f"is still pending for {group_name}. Please settle it today — "
            f"flagging for manual follow-up after this."
        ),
    }

    return templates[level]


def generate_reminder(
    member_name: str,
    amount: float,
    group_name: str,
    level: int
) -> str:
    """
    Generate an escalating reminder message.

    Escalation is strictly bounded to levels 1-3 regardless of caller input.
    """

    # Hard cap: the AI can NEVER move beyond level 3.
    level = max(
        1,
        min(3, int(level))
    )

    # Sanitize values used in the prompt.
    member_name = str(member_name).strip()[:100]
    group_name = str(group_name).strip()[:150]

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        amount = 0.0

    if not math.isfinite(amount) or amount < 0:
        amount = 0.0

    tone = REMINDER_TONES[level]

    # -----------------------------------------------------------------------
    # AI path
    # -----------------------------------------------------------------------

    if _client:
        prompt = (
            "Write a short WhatsApp-style payment reminder.\n\n"
            f"Person: {member_name}\n"
            f"Amount owed: ₹{amount:.2f}\n"
            f"Group: {group_name}\n"
            f"Tone: {tone}\n\n"
            "Requirements:\n"
            "- Keep it under 3 sentences.\n"
            "- Mention the exact amount.\n"
            "- Keep the tone natural and respectful.\n"
            "- Do not threaten, shame, or insult the person.\n"
            "- Do not claim that money has been collected.\n"
            "- Do not claim that the system can force a payment.\n"
            "- Do not include a greeting header or sign-off.\n"
            "- Return only the message body."
        )

        try:
            resp = _client.messages.create(
                model=MODEL,
                max_tokens=200,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            if resp.content:
                message = resp.content[0].text.strip()

                # Basic output validation.
                if (
                    message
                    and len(message) <= MAX_REMINDER_CHARS
                ):
                    return message

        except Exception:
            # Fall through to deterministic template.
            pass

    # -----------------------------------------------------------------------
    # Deterministic fallback
    # -----------------------------------------------------------------------

    return _fallback_reminder(
        member_name,
        amount,
        group_name,
        level
    )