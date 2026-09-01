"""Run `python seed.py` to populate a demo group with expenses so you can
record the pitch video without manual data entry."""
from sqlmodel import Session, select
from app.database import engine, init_db
from app.models import Group, Member, Expense, ExpenseShare
from app.settlement import compute_net_balances, simplify_debts

init_db()

with Session(engine) as session:
    group = Group(name="Goa Trip 2026")
    session.add(group)
    session.commit()
    session.refresh(group)

    names = ["Aarav", "Diya", "Kabir", "Meera", "Rohan"]
    members = []
    for n in names:
        m = Member(group_id=group.id, name=n)
        session.add(m)
        session.commit()
        session.refresh(m)
        members.append(m)

    def add_expense(desc, amount, paid_by, split_ids):
        e = Expense(group_id=group.id, description=desc, amount=amount, paid_by_member_id=paid_by)
        session.add(e)
        session.commit()
        session.refresh(e)
        share = round(amount / len(split_ids), 2)
        for mid in split_ids:
            session.add(ExpenseShare(expense_id=e.id, member_id=mid, amount_owed=share))
        session.commit()

    ids = [m.id for m in members]
    add_expense("Beach resort (2 nights)", 18000, members[0].id, ids)
    add_expense("Scuba diving", 6000, members[1].id, ids)
    add_expense("Dinner at Thalassa", 4200, members[2].id, ids)
    add_expense("Scooter rentals", 3000, members[3].id, [members[0].id, members[1].id, members[3].id])
    add_expense("Groceries & snacks", 1500, members[4].id, ids)

    print(f"Seeded group '{group.name}' (id={group.id}) with {len(members)} members and 5 expenses.")
    print(f"Visit http://localhost:8000/groups/{group.id} then click 'Recompute settlement'.")
