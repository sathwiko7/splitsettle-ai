# SplitSettle AI

**Razorpay AI Buildathon 2026 — Open Track**

An agent that closes group-expense loops the way Track 03/04 agents close finance-ops
loops: detect the problem (messy pairwise IOUs), determine the right intervention
(minimum-transfer settlement), and execute a bounded recovery workflow (escalating,
logged reminders) — end to end, with measured results, not a cherry-picked demo.

## The problem

Every trip, hostel mess, or event splits money N ways. People track it in a notes app
or a spreadsheet, the math gets confusing fast, nobody wants to be the one chasing
friends for ₹200, and it usually never gets fully settled. This is a problem every
student on this panel has lived — that's the "solve something you deeply understand"
bar for the Open Track.

## What it does

1. **Ledger** — log expenses per group, or paste a raw receipt and let AI extract
   line items instead of typing them in by hand.
2. **Settlement engine** — a debt-simplification algorithm (greedy max-creditor /
   max-debtor matching) collapses N-way IOUs into the minimum number of real
   transfers. This is the measurable core: naive settling needs up to `n(n-1)/2`
   transactions, this reduces it to at most `n-1`. The dashboard reports the
   actual % reduction for the current group, not a theoretical claim.
3. **Reminder agent** — for each unpaid transfer, an agent writes a personalized,
   escalating nudge (levels 1→3, capped — it never nags indefinitely) and marks
   status. Every single action (expense added, receipt parsed, settlement
   recomputed, reminder sent, payment marked) is written to an **audit log** with
   a timestamp and the exact message sent — the explainability judges want to see.
4. **Real payment collection** — each pending settlement can generate an actual
   Razorpay test-mode **Payment Link** (short_url a person can pay on the spot),
   and a "check payment status" action polls Razorpay's API to see if it's been
   paid. This is real settlement collection on Razorpay's own rails, not a
   simulated checkout.
5. **Metrics dashboard** — settlement efficiency %, recovery rate (settlements
   paid / total), and a live audit trail count, all computed from real data in
   the group, not hardcoded.

## Why this fits the bar

- **Real problem**: not invented for the hackathon — every group trip has this issue.
- **Working product**: full CRUD, a working algorithm with a citable complexity
  bound, and an agent loop, not a chatbot wrapper.
- **Meaningful AI use**: AI does two things a human would otherwise do manually —
  extract structured data from unstructured receipt text, and write natural,
  situationally-appropriate reminder copy. Both are optional-but-central: the app
  runs without an API key (deterministic fallback) so the core logic is provably
  the algorithm, not the LLM, and the LLM is provably additive on top.
- **Bounded and explainable**: reminder escalation caps at level 3. Every agent
  action is logged with its exact output — including the Payment Link ID, amount,
  and URL. The agent creates a payment request, it never moves money itself;
  the person who owes still has to click "pay" on Razorpay's own hosted checkout.
  This mirrors the "every money action explainable, bounded and gated" bar from
  the Growth track, applied here to a lower-stakes but real domain.
- **On Razorpay's own rails**: settlement collection runs through actual
  Razorpay test-mode Payment Links, not a mocked "pay" button — the project
  is Razorpay-native, not just AI-adjacent.
- **Evidence of value**: the dashboard shows *measured* settlement efficiency and
  recovery rate for the actual group in front of you, live, not a slide claim.
  Note the honest boundary though: efficiency (fewer transfers) is a mathematical
  guarantee of the algorithm, provable on any data. Recovery rate is real only
  once real people have actually paid a real link — on synthetic seed data it's
  demonstrative, not evidence of adoption. Be upfront about that distinction if
  a judge asks; it's more credible than overclaiming.

## Architecture

```
Browser (Jinja2-rendered dashboard, vanilla JS for the receipt-parse fetch call)
        │
        ▼
FastAPI app (app/main.py)
   ├── /groups, /members, /expenses         — ledger CRUD
   ├── /groups/{id}/receipt                 — AI receipt parsing (ai_agent.py)
   ├── /groups/{id}/compute-settlement      — settlement.py (debt simplification)
   ├── /settlements/{id}/remind             — AI reminder agent (ai_agent.py)
   ├── /settlements/{id}/create-payment-link — Razorpay Payment Link (razorpay_client.py)
   └── /settlements/{id}/sync-payment-status — polls Razorpay for paid status
        │                                        (every action writes AuditLog)
        ▼
SQLite via SQLModel (app/models.py)
   Group → Member → Expense → ExpenseShare
                  └→ Settlement (computed, holds payment_link_id/url) → AuditLog
        │
        ▼
Anthropic API (claude-sonnet-4-6)               Razorpay API (Payment Links, test mode)
optional — falls back to deterministic          optional — falls back to a local mock
rule-based parsing/templates if                 link if RAZORPAY_KEY_ID/SECRET are unset,
ANTHROPIC_API_KEY is unset.                      so the demo never breaks on stage.
```

## Running it

```bash
python -m venv venv && source venv/bin/activate     # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env                                 # optional: add your ANTHROPIC_API_KEY
python seed.py                                        # loads a demo group ("Goa Trip 2026")
uvicorn app.main:app --reload
```

Then open `http://localhost:8000`, go into "Goa Trip 2026", and click
**Recompute settlement** to see the algorithm run on real seeded data.

Without an `ANTHROPIC_API_KEY` set, receipt parsing and reminders still work
end-to-end via the rule-based fallback in `app/ai_agent.py` — good for a fast
local demo. Add the key for the full LLM-generated reminder copy and receipt
extraction.

Without `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET`, "Create payment link" generates
a mock link so the flow still demos end-to-end. Add test-mode keys (Dashboard >
Settings > API Keys > Test Mode, prefix `rzp_test_`) to get a real Razorpay
Payment Link you can actually open and pay in the browser — this is the piece
worth showing live in the pitch video, since a working test-mode payment
collected in real time is the strongest evidence you can put in front of a panel.

## 5-minute pitch outline

1. **0:00–0:45** — The problem, stated from lived experience (trip group chat,
   "who owes who," the spreadsheet nobody updates).
2. **0:45–2:00** — Live demo: paste a receipt → AI extracts items → add to ledger
   → click "Recompute settlement" → show the transfer count drop (e.g. 10 naive
   pairwise debts → 4 actual transfers) and explain the greedy algorithm in one
   sentence.
3. **2:00–3:00** — Click "Create payment link" on a pending settlement — show
   the real Razorpay test-mode link, open it, and actually pay it on camera if
   you have test keys set up. Click "Check payment status" and show it flip to
   `paid`, sourced from Razorpay's API, not a manual override.
4. **3:00–4:00** — Trigger a reminder on a different unpaid settlement, show the
   generated message, show the audit log entry with the exact text and
   timestamp. Emphasize the bounded escalation (caps at 3) and that the agent
   only ever creates a payment *request* — a human still has to pay it.
5. **4:00–5:00** — Metrics dashboard (efficiency %, recovery rate, audit count)
   and what's next: UPI deep-links, WhatsApp delivery for reminders, group spend
   analytics.

## What's stubbed vs. real

- **Real**: settlement algorithm, full CRUD, audit logging, metrics computation,
  the rule-based fallback for both AI functions, and — with test-mode keys set —
  real Razorpay Payment Link creation and status polling.
- **Stubbed without keys**: `RAZORPAY_KEY_ID`/`SECRET` unset falls back to a
  mock link (same response shape, can't actually be paid) so the flow still
  demos without setup. "Mark paid manually" stays available as a fallback for
  cash/UPI-outside-the-app settlements Razorpay wouldn't see anyway — worth
  naming explicitly in the pitch as a deliberate design choice, not a gap.

## Repo structure

```
splitsettle-ai/
├── app/
│   ├── main.py         FastAPI routes
│   ├── models.py       SQLModel schema
│   ├── database.py     engine/session
│   ├── settlement.py   debt-simplification algorithm
│   ├── ai_agent.py      receipt parsing + reminder generation (+ fallback)
│   └── razorpay_client.py  Payment Links integration (+ mock fallback)
├── templates/           Jinja2 HTML (ledger/receipt-themed UI)
├── static/style.css
├── seed.py               demo data for the pitch video
├── requirements.txt
└── .env.example
```
