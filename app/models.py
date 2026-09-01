"""
SplitSettle AI - data models

A "group" is a trip/hostel-mess/event.

Members owe / are owed money via Expenses,
which get collapsed into optimized Settlements by the
settlement engine.

The recovery agent then handles:
    payment links
    bounded reminders
    partial payments
    scheduled payments
    escalation

Every important agent action is recorded in AuditLog.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


# ============================================================
# GROUP
# ============================================================

class Group(SQLModel, table=True):
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    name: str

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
    )


# ============================================================
# MEMBER
# ============================================================

class Member(SQLModel, table=True):
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    group_id: int = Field(
        foreign_key="group.id",
    )

    name: str

    # Used to personalize reminder tone/messages.
    phone: Optional[str] = None


# ============================================================
# EXPENSE
# ============================================================

class Expense(SQLModel, table=True):
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    group_id: int = Field(
        foreign_key="group.id",
    )

    description: str

    amount: float

    paid_by_member_id: int = Field(
        foreign_key="member.id",
    )

    # manual | receipt_ai
    source: str = Field(
        default="manual",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
    )


# ============================================================
# EXPENSE SHARE
# ============================================================

class ExpenseShare(SQLModel, table=True):
    """
    How much of a given Expense each member owes.
    """

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    expense_id: int = Field(
        foreign_key="expense.id",
    )

    member_id: int = Field(
        foreign_key="member.id",
    )

    amount_owed: float


# ============================================================
# SETTLEMENT
# ============================================================

class Settlement(SQLModel, table=True):
    """
    A single optimized payment from debtor to creditor.

    Example:

        Original debt = ₹600

        paid_amount = ₹0
        remaining = ₹600

    After a ₹300 payment:

        paid_amount = ₹300
        remaining = ₹300
        status = "partially_paid"

    After another ₹300 payment:

        paid_amount = ₹600
        remaining = ₹0
        status = "paid"

    This allows SplitSettle to recover a settlement through
    multiple payment links without losing the original debt.
    """

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    group_id: int = Field(
        foreign_key="group.id",
    )

    from_member_id: int = Field(
        foreign_key="member.id",
    )

    to_member_id: int = Field(
        foreign_key="member.id",
    )

    # ---------------------------------------------------------
    # ORIGINAL DEBT
    # ---------------------------------------------------------

    amount: float

    # ---------------------------------------------------------
    # PAYMENT TRACKING
    # ---------------------------------------------------------

    """
    Total amount actually recovered so far.

    Example:

        amount = 600
        paid_amount = 300

        remaining = 300
    """

    paid_amount: float = Field(
        default=0.0,
    )

    # ---------------------------------------------------------
    # SETTLEMENT STATUS
    # ---------------------------------------------------------

    status: str = Field(
        default="pending",
    )

    # Possible values:
    #
    # pending
    # reminded
    # link_sent
    # partially_paid
    # paid

    # Number of automated reminders already sent.
    reminder_count: int = Field(
        default=0,
    )

    # ---------------------------------------------------------
    # RAZORPAY PAYMENT LINK
    # ---------------------------------------------------------

    """
    ID of the currently active Razorpay payment link.

    IMPORTANT:

    A settlement can have multiple payment links over time.

    Example:

        ₹600 debt
            ↓
        ₹300 link
            ↓
        paid
            ↓
        new ₹300 link
            ↓
        paid
    """

    payment_link_id: Optional[str] = None

    payment_link_url: Optional[str] = None

    """
    Amount represented by the CURRENT payment link.

    Example:

        Original settlement = ₹600
        Already paid        = ₹300

        payment_link_amount = ₹300
    """

    payment_link_amount: Optional[float] = None

    """
    Prevents the same Razorpay payment link from being
    counted more than once.

    Example:

        First status check:
            paid → count ₹300

        Second status check:
            paid → DO NOT count another ₹300
    """

    payment_link_paid: bool = Field(
        default=False,
    )

    # ---------------------------------------------------------
    # AI RECOVERY
    # ---------------------------------------------------------

    recovery_status: str = Field(
        default="none",
    )

    # Possible values:
    #
    # none
    # active
    # committed
    # completed
    # escalated

    recovery_option: Optional[str] = None

    # Possible values:
    #
    # full_payment
    # partial_payment
    # scheduled_payment

    """
    Amount the debtor has committed to pay as part of
    the current recovery decision.

    Example:

        Settlement = ₹600
        Recovery commitment = ₹300

        promised_amount = 300
    """

    promised_amount: Optional[float] = None

    """
    Used for scheduled payments.

    Stored as a string so the existing HTML date input
    can pass the value directly.
    """

    promised_date: Optional[str] = None

    """
    Optional note associated with the recovery decision.
    """

    recovery_note: Optional[str] = None

    # ---------------------------------------------------------
    # TIMESTAMP
    # ---------------------------------------------------------

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
    )


# ============================================================
# AUDIT LOG
# ============================================================

class AuditLog(SQLModel, table=True):
    """
    Every bounded agent action gets logged here.

    This is the audit trail for judges and for debugging.

    Examples:

        member_added
        expense_added
        receipt_parsed
        settlement_computed
        reminder_sent
        payment_link_created
        payment_status_synced
        partial_payment_received
        settlement_paid
        recovery_option_selected
        reminder_blocked
    """

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    group_id: int = Field(
        foreign_key="group.id",
    )

    settlement_id: Optional[int] = Field(
        default=None,
        foreign_key="settlement.id",
    )

    action: str

    """
    Human-readable description of what happened.

    Examples:

        "reminder_sent"
        "receipt_parsed"
        "settlement_computed"
        "payment_link_created"
        "partial_payment_received"
        "settlement_paid"
    """

    detail: str

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
    )