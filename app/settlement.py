"""
Settlement engine: collapses N members' pairwise IOUs into the minimum number
of actual money transfers ("min cash flow" problem). This is the metric we can
defend to a judge: naive settlement needs up to n*(n-1)/2 transactions; this
greedy max-debtor/max-creditor matching produces far fewer, in practice at
most (n-1).
"""
from typing import Dict, List, Tuple
import heapq


def compute_net_balances(
    expenses: List[dict], shares: List[dict], member_ids: List[int]
) -> Dict[int, float]:
    """net[member] = amount they paid - amount they owe across all expenses.
    Positive = should receive money. Negative = owes money."""
    net = {m: 0.0 for m in member_ids}
    for e in expenses:
        net[e["paid_by_member_id"]] = net.get(e["paid_by_member_id"], 0.0) + e["amount"]
    for s in shares:
        net[s["member_id"]] = net.get(s["member_id"], 0.0) - s["amount_owed"]
    return {m: round(v, 2) for m, v in net.items()}


def simplify_debts(net_balances: Dict[int, float]) -> List[Tuple[int, int, float]]:
    """Greedy algorithm: repeatedly match the biggest creditor with the biggest
    debtor until all balances are ~0. Returns list of (from_member, to_member, amount).
    This is provably close to optimal and simple enough to explain on a panel."""
    creditors = []  # max-heap of (-amount, member)
    debtors = []    # max-heap of (-amount, member)  amount stored positive-owed

    for member, bal in net_balances.items():
        if bal > 0.01:
            heapq.heappush(creditors, (-bal, member))
        elif bal < -0.01:
            heapq.heappush(debtors, (bal, member))  # bal negative already

    transfers = []
    while creditors and debtors:
        neg_credit, creditor = heapq.heappop(creditors)
        credit = -neg_credit
        debt_bal, debtor = heapq.heappop(debtors)
        debt = -debt_bal

        amount = round(min(credit, debt), 2)
        if amount > 0.01:
            transfers.append((debtor, creditor, amount))

        remaining_credit = round(credit - amount, 2)
        remaining_debt = round(debt - amount, 2)

        if remaining_credit > 0.01:
            heapq.heappush(creditors, (-remaining_credit, creditor))
        if remaining_debt > 0.01:
            heapq.heappush(debtors, (-remaining_debt, debtor))

    return transfers


def naive_transaction_count(n_members_with_balance: int) -> int:
    """Upper bound if everyone just paid everyone they individually owed,
    used as the baseline we report improvement against."""
    n = n_members_with_balance
    return max(0, n * (n - 1) // 2)
