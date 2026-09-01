from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlmodel import Session, select

from typing import Optional

from app.database import init_db, get_session
from app.models import (
    Group,
    Member,
    Expense,
    ExpenseShare,
    Settlement,
    AuditLog,
)
from app.settlement import (
    compute_net_balances,
    simplify_debts,
    naive_transaction_count,
)
from app import ai_agent
from app import razorpay_client


# ============================================================
# APP
# ============================================================

app = FastAPI(title="SplitSettle AI")

templates = Jinja2Templates(directory="templates")

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def on_startup():
    init_db()


# ============================================================
# HELPERS
# ============================================================

def get_group_or_redirect(
    group_id: int,
    session: Session,
):
    """
    Return the requested group.

    Routes use this helper so invalid group IDs don't cause
    unexpected database errors.
    """

    return session.get(Group, group_id)


def get_group_members(
    group_id: int,
    session: Session,
):
    """Return all members belonging to a group."""

    return session.exec(
        select(Member).where(
            Member.group_id == group_id
        )
    ).all()


def add_audit(
    session: Session,
    group_id: int,
    action: str,
    detail: str,
    settlement_id: Optional[int] = None,
):
    """
    Centralized audit-log helper.

    Every important workflow transition goes through this function.
    """

    session.add(
        AuditLog(
            group_id=group_id,
            settlement_id=settlement_id,
            action=action,
            detail=detail,
        )
    )


def create_expense_with_shares(
    session: Session,
    group_id: int,
    description: str,
    amount: float,
    paid_by: int,
    split_between: list[int],
    source: str = "manual",
):
    """
    Create an expense and its equal shares.

    Uses paise internally so the sum of all shares exactly equals
    the original expense amount.
    """

    # --------------------------------------------------------
    # Basic validation
    # --------------------------------------------------------

    description = str(description).strip()

    if not description:
        raise ValueError("Expense description cannot be empty.")

    if amount <= 0:
        raise ValueError("Expense amount must be greater than zero.")

    if len(split_between) == 0:
        raise ValueError("Expense must be split between at least one member.")

    # Remove duplicate IDs while preserving order.
    split_between = list(
        dict.fromkeys(
            int(member_id)
            for member_id in split_between
        )
    )

    paid_by = int(paid_by)

    # --------------------------------------------------------
    # Validate members belong to this group
    # --------------------------------------------------------

    group_members = get_group_members(
        group_id,
        session,
    )

    valid_member_ids = {
        int(member.id)
        for member in group_members
    }

    if paid_by not in valid_member_ids:
        raise ValueError(
            "The selected payer is not a member of this group."
        )

    invalid_split_members = [
        member_id
        for member_id in split_between
        if member_id not in valid_member_ids
    ]

    if invalid_split_members:
        raise ValueError(
            "One or more split members do not belong to this group."
        )

    # --------------------------------------------------------
    # Create expense
    # --------------------------------------------------------

    expense = Expense(
        group_id=group_id,
        description=description,
        amount=round(float(amount), 2),
        paid_by_member_id=paid_by,
        source=source,
    )

    session.add(expense)
    session.commit()
    session.refresh(expense)

    # --------------------------------------------------------
    # Exact paise split
    # --------------------------------------------------------

    total_paise = int(
        round(float(amount) * 100)
    )

    member_count = len(split_between)

    base_paise = total_paise // member_count
    remainder_paise = total_paise % member_count

    for index, member_id in enumerate(split_between):

        share_paise = base_paise

        if index < remainder_paise:
            share_paise += 1

        share_amount = share_paise / 100

        session.add(
            ExpenseShare(
                expense_id=expense.id,
                member_id=member_id,
                amount_owed=share_amount,
            )
        )

    session.commit()

    return expense


# ============================================================
# HOME / GROUPS
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def home(
    request: Request,
    session: Session = Depends(get_session),
):

    groups = session.exec(
        select(Group)
    ).all()

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "groups": groups,
        },
    )


@app.post("/groups")
def create_group(
    name: str = Form(...),
    session: Session = Depends(get_session),
):

    name = name.strip()

    if not name:
        return RedirectResponse(
            "/",
            status_code=303,
        )

    group = Group(
        name=name
    )

    session.add(group)
    session.commit()
    session.refresh(group)

    return RedirectResponse(
        f"/groups/{group.id}",
        status_code=303,
    )


# ============================================================
# GROUP DASHBOARD
# ============================================================

@app.get(
    "/groups/{group_id}",
    response_class=HTMLResponse,
)
def group_detail(
    group_id: int,
    request: Request,
    session: Session = Depends(get_session),
):

    group = get_group_or_redirect(
        group_id,
        session,
    )

    if not group:
        return RedirectResponse(
            "/",
            status_code=303,
        )

    members = get_group_members(
        group_id,
        session,
    )

    expenses = session.exec(
        select(Expense)
        .where(
            Expense.group_id == group_id
        )
    ).all()

    settlements = session.exec(
        select(Settlement)
        .where(
            Settlement.group_id == group_id
        )
    ).all()

    audit = session.exec(
        select(AuditLog)
        .where(
            AuditLog.group_id == group_id
        )
        .order_by(
            AuditLog.created_at.desc()
        )
    ).all()

    member_map = {
        m.id: m.name
        for m in members
    }

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    paid = sum(
        1
        for settlement in settlements
        if settlement.status == "paid"
    )

    total_settlements = len(
        settlements
    )

    recovery_rate = (
        round(
            100 * paid / total_settlements,
            1,
        )
        if total_settlements
        else 0.0
    )

    # Use only members with non-zero balances when computing
    # the naive comparison.
    shares = session.exec(
        select(ExpenseShare)
        .join(Expense)
        .where(
            Expense.group_id == group_id
        )
    ).all()

    member_ids = [
        m.id
        for m in members
    ]

    net = compute_net_balances(
        [e.model_dump() for e in expenses],
        [s.model_dump() for s in shares],
        member_ids,
    )

    active_members = [
        member_id
        for member_id in member_ids
        if abs(net.get(member_id, 0)) > 0.01
    ]

    naive_count = naive_transaction_count(
        len(active_members)
    )

    efficiency = (
        round(
            100 * (
                1 - total_settlements / naive_count
            ),
            1,
        )
        if naive_count
        else 0.0
    )

    return templates.TemplateResponse(
        "group.html",
        {
            "request": request,
            "group": group,
            "members": members,
            "member_map": member_map,
            "expenses": expenses,
            "settlements": settlements,
            "audit": audit,
            "settlement_remaining": settlement_remaining,
            "recovery_rate": recovery_rate,
            "efficiency": efficiency,
            "naive_count": naive_count,
            "total_settlements": total_settlements,
            "razorpay_live": razorpay_client.is_live(),
        },
    )


# ============================================================
# PAYMENT / RECOVERY HELPERS
# ============================================================

def settlement_remaining(settlement: Settlement) -> float:
    """
    Return the amount still owed on a settlement.

    The original settlement amount never changes. paid_amount records
    how much has already been recovered, so a ₹600 debt can correctly
    become ₹300 remaining after a ₹300 installment.
    """
    original = round(float(settlement.amount or 0), 2)
    paid = round(float(settlement.paid_amount or 0), 2)

    remaining = round(original - paid, 2)

    # Never allow a negative outstanding balance because of rounding.
    return max(0.0, remaining)


def normalize_money(value: float) -> float:
    """Normalize a money value to two decimal places."""
    return round(float(value), 2)


# ============================================================
# MEMBERS
# ============================================================

@app.post(
    "/groups/{group_id}/members"
)
def add_member(
    group_id: int,
    name: str = Form(...),
    phone: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):

    group = get_group_or_redirect(
        group_id,
        session,
    )

    if not group:
        return RedirectResponse(
            "/",
            status_code=303,
        )

    name = name.strip()

    if not name:
        return RedirectResponse(
            f"/groups/{group_id}",
            status_code=303,
        )

    # Prevent accidental duplicate member names.
    existing_members = get_group_members(
        group_id,
        session,
    )

    if any(
        member.name.strip().lower() == name.lower()
        for member in existing_members
    ):
        return RedirectResponse(
            f"/groups/{group_id}",
            status_code=303,
        )

    member = Member(
        group_id=group_id,
        name=name,
        phone=phone.strip() if phone else None,
    )

    session.add(member)

    add_audit(
        session,
        group_id,
        "member_added",
        f"Member '{name}' added to the group.",
    )

    session.commit()

    return RedirectResponse(
        f"/groups/{group_id}",
        status_code=303,
    )


# ============================================================
# EXPENSES
# ============================================================

@app.post(
    "/groups/{group_id}/expenses"
)
def add_expense(
    group_id: int,
    description: str = Form(...),
    amount: float = Form(...),
    paid_by: int = Form(...),
    split_between: list = Form(...),
    source: str = Form("manual"),
    session: Session = Depends(get_session),
):

    group = get_group_or_redirect(
        group_id,
        session,
    )

    if not group:
        return RedirectResponse(
            "/",
            status_code=303,
        )

    # Only these two sources are allowed.
    if source not in {
        "manual",
        "receipt_ai",
    }:
        source = "manual"

    try:

        expense = create_expense_with_shares(
            session=session,
            group_id=group_id,
            description=description,
            amount=amount,
            paid_by=paid_by,
            split_between=split_between,
            source=source,
        )

    except (ValueError, TypeError):

        return RedirectResponse(
            f"/groups/{group_id}",
            status_code=303,
        )

    add_audit(
        session,
        group_id,
        "expense_added",
        (
            f"'{expense.description}' "
            f"(₹{expense.amount:.2f}) "
            f"split between "
            f"{len(set(int(x) for x in split_between))} members "
            f"via {expense.source}"
        ),
    )

    session.commit()

    return RedirectResponse(
        f"/groups/{group_id}",
        status_code=303,
    )


# ============================================================
# AI RECEIPT PARSING
# ============================================================

@app.post(
    "/groups/{group_id}/receipt"
)
def parse_receipt(
    group_id: int,
    receipt_text: str = Form(...),
    session: Session = Depends(get_session),
):

    group = get_group_or_redirect(
        group_id,
        session,
    )

    if not group:
        return JSONResponse(
            {
                "items": [],
                "error": "Group not found.",
            },
            status_code=404,
        )

    receipt_text = receipt_text.strip()

    if not receipt_text:
        return JSONResponse(
            {
                "items": [],
                "error": "Receipt text is empty.",
            },
            status_code=400,
        )

    try:

        items = ai_agent.parse_receipt_text(
            receipt_text
        )

    except Exception:

        items = []

    # --------------------------------------------------------
    # Audit the parse attempt
    # --------------------------------------------------------

    add_audit(
        session,
        group_id,
        "receipt_parsed",
        (
            f"AI extracted {len(items)} "
            f"validated line items from pasted receipt text."
        ),
    )

    session.commit()

    return {
        "items": items
    }


# ============================================================
# AI RECEIPT → LEDGER
# ============================================================

@app.post(
    "/groups/{group_id}/receipt/add-expense"
)
def add_receipt_expense(
    group_id: int,
    description: str = Form(...),
    amount: float = Form(...),
    paid_by: int = Form(...),
    split_between: list = Form(...),
    session: Session = Depends(get_session),
):

    """
    Create an actual ledger expense from an AI-extracted receipt item.

    This is deliberately a normal expense-creation path with
    source='receipt_ai'. The AI suggests structured data; the
    user still chooses the payer and participants before the
    expense enters the financial ledger.
    """

    group = get_group_or_redirect(
        group_id,
        session,
    )

    if not group:
        return JSONResponse(
            {
                "ok": False,
                "error": "Group not found.",
            },
            status_code=404,
        )

    try:

        expense = create_expense_with_shares(
            session=session,
            group_id=group_id,
            description=description,
            amount=amount,
            paid_by=paid_by,
            split_between=split_between,
            source="receipt_ai",
        )

    except (ValueError, TypeError) as exc:

        session.rollback()

        return JSONResponse(
            {
                "ok": False,
                "error": str(exc),
            },
            status_code=400,
        )

    add_audit(
        session,
        group_id,
        "receipt_expense_added",
        (
            f"AI-extracted item '{expense.description}' "
            f"(₹{expense.amount:.2f}) added to ledger; "
            f"payer={paid_by}; "
            f"split_between={len(set(int(x) for x in split_between))} members."
        ),
    )

    session.commit()

    return {
        "ok": True,
        "expense_id": expense.id,
        "description": expense.description,
        "amount": expense.amount,
        "source": expense.source,
    }


# ============================================================
# SETTLEMENT ENGINE
# ============================================================

@app.post(
    "/groups/{group_id}/compute-settlement"
)
def compute_settlement(
    group_id: int,
    session: Session = Depends(get_session),
):

    group = get_group_or_redirect(
        group_id,
        session,
    )

    if not group:
        return RedirectResponse(
            "/",
            status_code=303,
        )

    members = get_group_members(
        group_id,
        session,
    )

    expenses = session.exec(
        select(Expense)
        .where(
            Expense.group_id == group_id
        )
    ).all()

    shares = session.exec(
        select(ExpenseShare)
        .join(Expense)
        .where(
            Expense.group_id == group_id
        )
    ).all()

    member_ids = [
        m.id
        for m in members
    ]

    # --------------------------------------------------------
    # 1. Calculate the balance from the original expense ledger.
    # --------------------------------------------------------

    net = compute_net_balances(
        [e.model_dump() for e in expenses],
        [s.model_dump() for s in shares],
        member_ids,
    )

    # --------------------------------------------------------
    # 2. PRESERVE existing settlements.
    #
    # Recompute used to delete every unpaid settlement and rebuild
    # it from the original ledger. That caused a recovery settlement
    # such as ₹600 -> ₹300 + ₹300 to suddenly become ₹600 again.
    #
    # Existing settlements already represent obligations in the
    # ledger, so remove their ORIGINAL amounts from the residual
    # balance before looking for genuinely new transfers.
    # --------------------------------------------------------

    existing_settlements = session.exec(
        select(Settlement)
        .where(
            Settlement.group_id == group_id
        )
    ).all()

    for settlement in existing_settlements:
        represented_amount = normalize_money(
            settlement.amount
        )

        if represented_amount <= 0.01:
            continue

        debtor_id = settlement.from_member_id
        creditor_id = settlement.to_member_id

        # Remove this already-created obligation from the residual
        # ledger. The Settlement record itself remains untouched,
        # including paid_amount, recovery state and payment-link data.
        net[debtor_id] = normalize_money(
            net.get(debtor_id, 0.0) + represented_amount
        )

        net[creditor_id] = normalize_money(
            net.get(creditor_id, 0.0) - represented_amount
        )

    residual_net = {
        member_id: normalize_money(balance)
        for member_id, balance in net.items()
    }

    # --------------------------------------------------------
    # 3. Calculate only transfers that are not already represented
    #    by an existing Settlement record.
    # --------------------------------------------------------

    transfers = simplify_debts(
        residual_net
    )

    existing_pairs = {
        (
            settlement.from_member_id,
            settlement.to_member_id,
        )
        for settlement in existing_settlements
        if settlement.status != "paid"
    }

    new_transfers = []

    for from_id, to_id, amount in transfers:
        amount = normalize_money(amount)

        if amount <= 0.01:
            continue

        # Do not create a duplicate outstanding settlement for a
        # pair that already has an active settlement/recovery plan.
        if (from_id, to_id) in existing_pairs:
            continue

        session.add(
            Settlement(
                group_id=group_id,
                from_member_id=from_id,
                to_member_id=to_id,
                amount=amount,
            )
        )

        new_transfers.append(
            (from_id, to_id, amount)
        )

        existing_pairs.add(
            (from_id, to_id)
        )

    # --------------------------------------------------------
    # 4. Metrics
    # --------------------------------------------------------

    active_members = [
        member_id
        for member_id in member_ids
        if abs(residual_net.get(member_id, 0)) > 0.01
    ]

    naive = naive_transaction_count(
        len(active_members)
    )

    active_existing_count = len(
        [
            settlement
            for settlement in existing_settlements
            if settlement.status != "paid"
        ]
    )

    total_active_transfers = (
        active_existing_count + len(new_transfers)
    )

    efficiency = (
        round(
            100 * (
                1 - total_active_transfers / naive
            ),
            1,
        )
        if naive
        else 0.0
    )

    add_audit(
        session,
        group_id,
        "settlement_recomputed",
        (
            f"Settlement recomputed without deleting existing "
            f"recovery/payment state. "
            f"{len(new_transfers)} new transfer(s) created; "
            f"{len(existing_settlements)} existing settlement(s) preserved."
        ),
    )

    session.commit()

    return RedirectResponse(
        f"/groups/{group_id}",
        status_code=303,
    )


# ============================================================
# REMINDER AGENT
# ============================================================

@app.post(
    "/settlements/{settlement_id}/remind"
)
def send_reminder(
    settlement_id: int,
    session: Session = Depends(get_session),
):

    settlement = session.get(
        Settlement,
        settlement_id,
    )

    if not settlement:
        return RedirectResponse(
            "/",
            status_code=303,
        )

    group_id = settlement.group_id

    if settlement.status == "paid":
        return RedirectResponse(
            f"/groups/{group_id}",
            status_code=303,
        )

    # --------------------------------------------------------
    # HARD CAP
    # --------------------------------------------------------

    if settlement.reminder_count >= 3:

        add_audit(
            session,
            group_id,
            "reminder_blocked",
            (
                f"Reminder blocked for settlement #{settlement.id}: "
                f"automated reminder cap of 3 already reached."
            ),
            settlement_id=settlement.id,
        )

        session.commit()

        return RedirectResponse(
            f"/groups/{group_id}",
            status_code=303,
        )

    from_member = session.get(
        Member,
        settlement.from_member_id,
    )

    group = session.get(
        Group,
        settlement.group_id,
    )

    if not from_member or not group:
        return RedirectResponse(
            f"/groups/{group_id}",
            status_code=303,
        )

    # Level can only be 1, 2, or 3.
    level = min(
        settlement.reminder_count + 1,
        3,
    )

    try:

        message = ai_agent.generate_reminder(
            from_member.name,
            settlement_remaining(settlement),
            group.name,
            level,
        )

    except Exception:

        message = (
            f"{from_member.name}, ₹{settlement_remaining(settlement):.2f} "
            f"is still pending for {group.name}. "
            f"Please settle it when you can."
        )

    settlement.reminder_count = level
    settlement.status = "reminded"

    session.add(
        settlement
    )

    add_audit(
        session,
        group_id,
        "reminder_sent",
        (
            f'Level {level}/3 to {from_member.name}: '
            f'"{message}"'
        ),
        settlement_id=settlement.id,
    )

    session.commit()

    return RedirectResponse(
        f"/groups/{group_id}",
        status_code=303,
    )


# ============================================================
# RAZORPAY PAYMENT LINKS
# ============================================================

@app.post(
    "/settlements/{settlement_id}/create-payment-link"
)
def create_payment_link(
    settlement_id: int,
    session: Session = Depends(get_session),
):
    """
    Create a Razorpay link only for the CURRENT outstanding amount.

    Example:
        Original settlement = ₹600
        paid_amount        = ₹300
        remaining           = ₹300

    The next link is therefore created for ₹300, not ₹600.
    """

    settlement = session.get(
        Settlement,
        settlement_id,
    )

    if not settlement:
        return RedirectResponse(
            "/",
            status_code=303,
        )

    group_id = settlement.group_id

    if settlement.status == "paid":
        return RedirectResponse(
            f"/groups/{group_id}",
            status_code=303,
        )

    remaining = settlement_remaining(settlement)

    if remaining <= 0:
        settlement.paid_amount = round(
            min(float(settlement.paid_amount or 0), float(settlement.amount)),
            2,
        )
        settlement.status = "paid"
        settlement.recovery_status = "completed"
        session.add(settlement)

        add_audit(
            session,
            group_id,
            "settlement_already_complete",
            (
                f"Settlement #{settlement.id} has no remaining balance. "
                f"Original=₹{settlement.amount:.2f}; "
                f"paid=₹{settlement.paid_amount:.2f}."
            ),
            settlement_id=settlement.id,
        )

        session.commit()

        return RedirectResponse(
            f"/groups/{group_id}",
            status_code=303,
        )

    # A currently active link must be checked/used before another one
    # is created. Once its payment is recorded, the link ID is cleared.
    if settlement.payment_link_id:
        return RedirectResponse(
            f"/groups/{group_id}",
            status_code=303,
        )

    from_member = session.get(
        Member,
        settlement.from_member_id,
    )

    to_member = session.get(
        Member,
        settlement.to_member_id,
    )

    group = session.get(
        Group,
        settlement.group_id,
    )

    if not from_member or not to_member or not group:
        return RedirectResponse(
            f"/groups/{group_id}",
            status_code=303,
        )

    # Create the link ONLY for the amount still outstanding.
    link_amount = remaining

    try:
        link = razorpay_client.create_payment_link(
            reference_id=f"settle-{settlement.id}-{int(link_amount * 100)}",
            amount_rupees=link_amount,
            description=(
                f"{group.name}: "
                f"{from_member.name} owes "
                f"{to_member.name} "
                f"(₹{link_amount:.2f} remaining)"
            ),
            customer_name=from_member.name,
        )

    except Exception as exc:
        add_audit(
            session,
            group_id,
            "payment_link_failed",
            (
                f"Could not create Razorpay Payment Link "
                f"for settlement #{settlement.id}: {exc}"
            ),
            settlement_id=settlement.id,
        )

        session.commit()

        return RedirectResponse(
            f"/groups/{group_id}",
            status_code=303,
        )

    settlement.payment_link_id = link["id"]
    settlement.payment_link_url = link["short_url"]
    settlement.payment_link_amount = link_amount
    settlement.payment_link_paid = False
    settlement.status = "link_sent"

    session.add(settlement)

    mode = (
        "LIVE"
        if razorpay_client.is_live()
        else "MOCK"
    )

    add_audit(
        session,
        group_id,
        "payment_link_created",
        (
            f"{mode} Razorpay link "
            f"{link['id']} for CURRENT outstanding amount "
            f"₹{link_amount:.2f} "
            f"(original=₹{settlement.amount:.2f}, "
            f"already_paid=₹{settlement.paid_amount:.2f}) "
            f"({from_member.name} → {to_member.name}): "
            f"{link['short_url']}"
        ),
        settlement_id=settlement.id,
    )

    session.commit()

    return RedirectResponse(
        f"/groups/{group_id}",
        status_code=303,
    )


# ============================================================
# RAZORPAY PAYMENT STATUS
# ============================================================

@app.post(
    "/settlements/{settlement_id}/sync-payment-status"
)
def sync_payment_status(
    settlement_id: int,
    session: Session = Depends(get_session),
):
    """
    Sync the CURRENT Razorpay payment link.

    Critical behavior:
        ₹600 settlement
        ↓
        ₹300 payment link
        ↓
        link paid
        ↓
        paid_amount = ₹300
        remaining = ₹300
        status = partially_paid
        payment_link_id is cleared
        ↓
        next "Pay" action creates a NEW ₹300 link
        ↓
        second ₹300 payment
        ↓
        paid_amount = ₹600
        remaining = ₹0
        status = paid

    A repeated status check cannot count the same link twice because
    payment_link_paid is set before the link is cleared.
    """

    settlement = session.get(
        Settlement,
        settlement_id,
    )

    if not settlement:
        return RedirectResponse(
            "/",
            status_code=303,
        )

    group_id = settlement.group_id

    if not settlement.payment_link_id:
        return RedirectResponse(
            f"/groups/{group_id}",
            status_code=303,
        )

    current_link_id = settlement.payment_link_id
    current_link_amount = normalize_money(
        settlement.payment_link_amount
        if settlement.payment_link_amount is not None
        else settlement_remaining(settlement)
    )

    try:
        status = razorpay_client.get_link_status(
            current_link_id
        )

    except Exception as exc:
        add_audit(
            session,
            group_id,
            "payment_status_check_failed",
            (
                f"Could not check Razorpay link "
                f"{current_link_id}: {exc}"
            ),
            settlement_id=settlement.id,
        )

        session.commit()

        return RedirectResponse(
            f"/groups/{group_id}",
            status_code=303,
        )

    detail = (
        f"Razorpay reports link "
        f"{current_link_id} "
        f"status = '{status}'"
    )

    # --------------------------------------------------------
    # PAYMENT COMPLETED FOR THIS LINK
    # --------------------------------------------------------
    if status == "paid":

        # Idempotency guard.
        # If this exact link was already processed, do not add the
        # same installment to paid_amount again.
        if not settlement.payment_link_paid:

            old_paid = normalize_money(
                settlement.paid_amount or 0
            )

            original_amount = normalize_money(
                settlement.amount
            )

            new_paid = min(
                original_amount,
                normalize_money(
                    old_paid + current_link_amount
                ),
            )

            settlement.paid_amount = new_paid
            settlement.payment_link_paid = True

            remaining = normalize_money(
                original_amount - new_paid
            )

            if remaining <= 0:
                # Entire original settlement is now recovered.
                settlement.paid_amount = original_amount
                settlement.status = "paid"
                settlement.recovery_status = "completed"

                detail += (
                    f"; installment=₹{current_link_amount:.2f}; "
                    f"paid_total=₹{settlement.paid_amount:.2f}; "
                    f"remaining=₹0.00; "
                    f"settlement COMPLETED"
                )

                add_audit(
                    session,
                    group_id,
                    "settlement_paid",
                    detail,
                    settlement_id=settlement.id,
                )

                # The link is no longer needed.
                settlement.payment_link_id = None
                settlement.payment_link_url = None
                settlement.payment_link_amount = None
                settlement.payment_link_paid = False

            else:
                # Only part of the original settlement has been
                # recovered. Keep the settlement open.
                settlement.status = "partially_paid"

                detail += (
                    f"; installment=₹{current_link_amount:.2f}; "
                    f"paid_total=₹{settlement.paid_amount:.2f}; "
                    f"remaining=₹{remaining:.2f}; "
                    f"settlement still OPEN"
                )

                add_audit(
                    session,
                    group_id,
                    "partial_payment_received",
                    detail,
                    settlement_id=settlement.id,
                )

                # Clear the consumed link so the next payment action
                # can create a NEW link for exactly the remaining amount.
                settlement.payment_link_id = None
                settlement.payment_link_url = None
                settlement.payment_link_amount = None
                settlement.payment_link_paid = False

        else:
            # Defensive branch for repeated processing.
            detail += (
                "; this payment link was already processed; "
                "no additional amount was added"
            )

            add_audit(
                session,
                group_id,
                "payment_status_already_processed",
                detail,
                settlement_id=settlement.id,
            )

    # --------------------------------------------------------
    # LINK EXISTS BUT HAS NOT BEEN FULLY PAID
    # --------------------------------------------------------
    elif status in {
        "created",
        "partially_paid",
    }:
        if settlement.status != "paid":
            settlement.status = "link_sent"

        add_audit(
            session,
            group_id,
            "payment_status_synced",
            detail,
            settlement_id=settlement.id,
        )

    else:
        # Expired/cancelled links remain visible through the audit
        # trail. They are NOT counted as paid.
        add_audit(
            session,
            group_id,
            "payment_status_synced",
            detail,
            settlement_id=settlement.id,
        )

    session.add(settlement)
    session.commit()

    return RedirectResponse(
        f"/groups/{group_id}",
        status_code=303,
    )


# ============================================================
# MANUAL PAYMENT FALLBACK
# ============================================================

@app.post(
    "/settlements/{settlement_id}/mark-paid"
)
def mark_paid(
    settlement_id: int,
    session: Session = Depends(get_session),
):
    """
    Manual/external payment fallback.

    This marks the FULL remaining balance as paid and updates
    paid_amount instead of only changing the status flag.
    """

    settlement = session.get(
        Settlement,
        settlement_id,
    )

    if not settlement:
        return RedirectResponse(
            "/",
            status_code=303,
        )

    if settlement.status == "paid":
        return RedirectResponse(
            f"/groups/{settlement.group_id}",
            status_code=303,
        )

    remaining = settlement_remaining(settlement)

    settlement.paid_amount = normalize_money(
        settlement.amount
    )
    settlement.status = "paid"
    settlement.recovery_status = "completed"

    # Any currently stored link is no longer actionable after a
    # manual full settlement.
    settlement.payment_link_id = None
    settlement.payment_link_url = None
    settlement.payment_link_amount = None
    settlement.payment_link_paid = False

    session.add(settlement)

    add_audit(
        session,
        settlement.group_id,
        "settlement_paid",
        (
            f"₹{remaining:.2f} remaining balance marked as paid manually. "
            f"Total recovered = ₹{settlement.paid_amount:.2f} "
            f"of ₹{settlement.amount:.2f}. "
            f"This may represent cash or an external UPI transfer."
        ),
        settlement_id=settlement.id,
    )

    session.commit()

    return RedirectResponse(
        f"/groups/{settlement.group_id}",
        status_code=303,
    )


# ============================================================
# AI RECOVERY DECISION
# ============================================================

@app.post("/settlements/{settlement_id}/recovery")
def choose_recovery_option(
    settlement_id: int,
    recovery_option: str = Form(...),
    promised_amount: Optional[float] = Form(None),
    promised_date: Optional[str] = Form(None),
    split_amount_1: Optional[float] = Form(None),
    split_date_1: Optional[str] = Form(None),
    split_amount_2: Optional[float] = Form(None),
    split_date_2: Optional[str] = Form(None),
    recovery_note: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    settlement = session.get(Settlement, settlement_id)

    if not settlement:
        return RedirectResponse("/", status_code=303)

    group_id = settlement.group_id

    if settlement.status == "paid":
        return RedirectResponse(
            f"/groups/{group_id}",
            status_code=303,
        )

    allowed_options = {
        "full_payment",
        "partial_payment",
        "split_payment",
        "scheduled_payment",
    }

    if recovery_option not in allowed_options:
        return RedirectResponse(
            f"/groups/{group_id}",
            status_code=303,
        )

    # --------------------------------------------------------
    # Validate recovery choice
    # --------------------------------------------------------

    if recovery_option == "partial_payment":
        if promised_amount is None:
            promised_amount = settlement_remaining(settlement)

        promised_amount = float(promised_amount)

        if promised_amount <= 0:
            return RedirectResponse(
                f"/groups/{group_id}",
                status_code=303,
            )

        if promised_amount > settlement_remaining(settlement):
            promised_amount = settlement_remaining(settlement)

    elif recovery_option == "split_payment":
        # Split recovery is intentionally bounded to exactly two installments.
        # The existing Settlement model stores the first commitment directly;
        # the second installment is retained in recovery_note for the demo/audit trail.
        remaining = settlement_remaining(settlement)

        if not split_date_1 or not split_date_2:
            return RedirectResponse(
                f"/groups/{group_id}",
                status_code=303,
            )

        try:
            first = float(split_amount_1) if split_amount_1 is not None else round(remaining / 2, 2)
            second = float(split_amount_2) if split_amount_2 is not None else round(remaining - first, 2)
        except (TypeError, ValueError):
            return RedirectResponse(
                f"/groups/{group_id}",
                status_code=303,
            )

        if first <= 0 or second <= 0:
            return RedirectResponse(
                f"/groups/{group_id}",
                status_code=303,
            )

        # Both installments must account for the complete outstanding balance.
        if abs((first + second) - remaining) > 0.01:
            return RedirectResponse(
                f"/groups/{group_id}",
                status_code=303,
            )

        promised_amount = round(first, 2)
        promised_date = split_date_1
        split_schedule = (
            f"Split schedule: ₹{first:.2f} on {split_date_1}; "
            f"₹{second:.2f} on {split_date_2}."
        )
        recovery_note = (
            f"{split_schedule} "
            f"{recovery_note.strip()}"
            if recovery_note and recovery_note.strip()
            else split_schedule
        )

    elif recovery_option == "scheduled_payment":
        if not promised_date:
            return RedirectResponse(
                f"/groups/{group_id}",
                status_code=303,
            )

        if promised_amount is None:
            promised_amount = settlement.amount

        promised_amount = float(promised_amount)

        if promised_amount <= 0:
            return RedirectResponse(
                f"/groups/{group_id}",
                status_code=303,
            )

        if promised_amount > settlement_remaining(settlement):
            promised_amount = settlement_remaining(settlement)

    else:
        promised_amount = settlement_remaining(settlement)
        promised_date = None

    # --------------------------------------------------------
    # Store AI recovery decision
    # --------------------------------------------------------

    settlement.recovery_status = "committed"
    settlement.recovery_option = recovery_option
    settlement.promised_amount = round(promised_amount, 2)
    settlement.promised_date = promised_date
    settlement.recovery_note = (
        recovery_note.strip()
        if recovery_note
        else None
    )

    # IMPORTANT: a link may have been created before the recovery decision.
    # That link can represent the old full balance. Replace it locally with
    # a fresh link for the amount being recovered NOW. For split recovery,
    # this is installment #1. The ledger settlement.amount stays unchanged.
    old_link_id = settlement.payment_link_id
    old_link_amount = settlement.payment_link_amount

    settlement.payment_link_id = None
    settlement.payment_link_url = None
    settlement.payment_link_amount = None
    settlement.payment_link_paid = False

    session.add(settlement)

    # --------------------------------------------------------
    # Create a payment link for the CURRENT recovery commitment
    # --------------------------------------------------------

    from_member = session.get(Member, settlement.from_member_id)
    to_member = session.get(Member, settlement.to_member_id)
    group = session.get(Group, settlement.group_id)

    if from_member and to_member and group and promised_amount > 0:
        try:
            recovery_link = razorpay_client.create_payment_link(
                reference_id=(
                    f"recovery-{settlement.id}-"
                    f"{int(promised_amount * 100)}"
                ),
                amount_rupees=round(promised_amount, 2),
                description=(
                    f"{group.name}: "
                    f"{from_member.name} owes "
                    f"{to_member.name} "
                    f"(recovery installment ₹{promised_amount:.2f})"
                ),
                customer_name=from_member.name,
            )

            settlement.payment_link_id = recovery_link["id"]
            settlement.payment_link_url = recovery_link["short_url"]
            settlement.payment_link_amount = round(promised_amount, 2)
            settlement.payment_link_paid = False
            settlement.status = "link_sent"

            add_audit(
                session,
                group_id,
                "recovery_payment_link_created",
                (
                    f"New recovery payment link {recovery_link['id']} "
                    f"created for CURRENT commitment ₹{promised_amount:.2f} "
                    f"(option={recovery_option}). "
                    f"Previous local link"
                    f"{f' {old_link_id}' if old_link_id else ''} "
                    f"for ₹{float(old_link_amount or 0):.2f} was superseded."
                ),
                settlement_id=settlement.id,
            )

        except Exception as exc:
            # Keep the recovery decision even if Razorpay is temporarily
            # unavailable. The dashboard can create a fresh link later.
            add_audit(
                session,
                group_id,
                "recovery_payment_link_failed",
                (
                    f"Recovery decision saved, but a new payment link "
                    f"for ₹{promised_amount:.2f} could not be created: {exc}"
                ),
                settlement_id=settlement.id,
            )

    # --------------------------------------------------------
    # Audit trail
    # --------------------------------------------------------

    option_labels = {
        "full_payment": "Full payment",
        "partial_payment": "Partial payment",
        "split_payment": "Split payment",
        "scheduled_payment": "Scheduled payment",
    }

    detail = (
        f"Recovery commitment selected: "
        f"{option_labels[recovery_option]}; "
        f"amount=₹{promised_amount:.2f}; "
        f"current_outstanding=₹{settlement_remaining(settlement):.2f}"
    )

    if promised_date:
        detail += f"; date={promised_date}"

    if recovery_note:
        detail += f"; note={recovery_note.strip()}"

    add_audit(
        session,
        group_id,
        "recovery_option_selected",
        detail,
        settlement_id=settlement.id,
    )

    session.commit()

    return RedirectResponse(
        f"/groups/{group_id}",
        status_code=303,
    )