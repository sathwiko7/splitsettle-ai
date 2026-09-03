# SplitSettle AI

### AI-powered group expense settlement and payment recovery

> **Splitting isn't the problem. Settling is.**

[![Razorpay AI Buildathon 2026](https://img.shields.io/badge/Razorpay-AI%20Buildathon%202026-blueviolet)](https://razorpay.com/)
[![Python](https://img.shields.io/badge/Python-3.x-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)](https://fastapi.tiangolo.com/)
[![Razorpay](https://img.shields.io/badge/Razorpay-Test%20Mode-528FF0)](https://razorpay.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](#license)

**SplitSettle AI** is an AI-powered group expense settlement agent built for the **Razorpay AI Buildathon 2026 — Open Track**.

Instead of stopping at:

> "Rahul owes Sneha ₹1,200."

SplitSettle AI tries to close the entire loop:

**Understand → Optimize → Execute → Recover → Settle**

It turns messy group expenses into optimized settlement transfers, creates Razorpay payment requests, handles structured recovery for unpaid obligations, generates contextual reminders, supports partial payments, and records important actions in an audit trail.

---

## 🚀 Live Demo

### 🌐 Try SplitSettle AI

**https://splitsettle-ai-5622.onrender.com**

> The deployed application uses Razorpay Test Mode for payment-link functionality.

### 🎥 Demo Video

**https://youtu.be/IKn3-EWvbEQ**

The demo walks through the complete product flow, including expense entry, AI receipt extraction, settlement optimization, Razorpay payment links, recovery workflows, partial payments, and the audit trail.

---

# 🧩 The Problem

Group expenses are easy to create but surprisingly difficult to finish.

Think about:

- College trips
- Hostel expenses
- Roommates
- Team lunches
- Events
- Group projects
- Vacations

A typical flow looks like:

```text
Someone pays
      ↓
Everyone owes different amounts
      ↓
People calculate balances manually
      ↓
"Who owes whom?"
      ↓
Someone forgets to pay
      ↓
Someone starts sending reminders
      ↓
The settlement remains unfinished
```

Most expense-splitting applications focus heavily on **calculating the split**.

But calculation is only the beginning.

The real problem is:

> **How do we actually close the outstanding financial obligations?**

SplitSettle AI focuses on the part that usually gets left unfinished:

## **Settlement → Payment → Recovery → Completion**

---

# 💡 The Solution

SplitSettle AI treats group expense settlement as a complete workflow rather than just a calculator.

### 1. Understand

Users can enter expenses manually or paste raw receipt/OCR text.

The AI receipt parser converts unstructured text into structured expense items.

```text
Raw receipt text
       ↓
AI extraction
       ↓
Structured items
       ↓
Expense ledger
```

---

### 2. Optimize

The settlement engine calculates each member's net balance.

Instead of generating unnecessary pairwise transactions, SplitSettle simplifies the debt graph into the transfers that are actually required.

For example:

```text
Before:

A → B
A → C
B → C
C → D
A → D
B → D
...

After optimization:

A → C
B → D
C → D
```

The goal is to minimize the number of real transfers required to settle the group.

The dashboard compares the optimized settlement against a naive pairwise baseline and reports the reduction for the current group.

---

### 3. Execute

Once an outstanding settlement exists, SplitSettle can create a **Razorpay Test Mode Payment Link**.

```text
Outstanding settlement
        ↓
Create Razorpay Payment Link
        ↓
Share payment request
        ↓
Person pays through Razorpay
        ↓
Check payment status
        ↓
Update settlement state
```

The application does not move money autonomously.

The person who owes the money still has to complete the payment through Razorpay.

---

### 4. Recover

What happens when someone cannot pay immediately?

Instead of leaving the obligation as:

> Payment Pending

SplitSettle provides a structured recovery workflow.

A user can:

- Pay the full outstanding amount
- Split the obligation into installments
- Choose installment dates
- Schedule a later payment
- Add a note explaining the commitment
- Continue tracking the remaining balance

Example:

```text
Outstanding: ₹1,200

Option A
Pay ₹1,200 now

Option B
₹600 → Date 1
₹600 → Date 2

Option C
Schedule payment for a later date
```

---

### 5. Settle

Partial payments are tracked as well.

For example:

```text
Original obligation: ₹1,200

Payment 1: ₹600
Remaining: ₹600

Settlement status:
PARTIALLY PAID
```

The remaining amount can continue through the recovery workflow.

The objective is simple:

> **Don't just calculate the debt. Help close it.**

---

# 🤖 Where AI Is Actually Used

SplitSettle AI deliberately does **not** use an LLM for everything.

Financially sensitive calculations should be deterministic.

AI is used where interpretation and language generation are useful.

## AI Capability 1 — Receipt Understanding

Users can paste messy receipt/OCR text such as:

```text
Pizza Margherita     ₹450
Cold Drinks          ₹180
French Fries         ₹220
Total                ₹850
```

The AI layer extracts structured items that can be added to the expense ledger.

This eliminates unnecessary manual data entry.

---

## AI Capability 2 — Recovery Assistance

The recovery layer generates contextual reminder messages for outstanding settlements.

Instead of sending the same generic message every time:

> "Please pay me."

SplitSettle can generate a more situational reminder based on the outstanding obligation and recovery state.

Reminder escalation is intentionally bounded rather than continuing indefinitely.

---

# 🛡️ AI Safety Boundary

A key design decision in SplitSettle AI is:

> **AI interprets. Deterministic code calculates.**

The LLM is **not responsible for calculating financial balances**.

The settlement engine performs the correctness-critical calculations.

This provides:

- Predictability
- Explainability
- Reproducibility
- Easier testing
- Lower risk of LLM arithmetic errors

The AI layer adds intelligence where natural-language understanding is valuable without putting financial correctness behind an LLM.

---

# 💳 Razorpay Integration

SplitSettle AI integrates with **Razorpay Payment Links in Test Mode**.

The payment flow is:

```text
Settlement generated
       ↓
Outstanding amount identified
       ↓
Razorpay Payment Link created
       ↓
Payment request shared
       ↓
User completes payment
       ↓
SplitSettle checks Razorpay status
       ↓
Settlement updated
```

The application uses Razorpay as the payment execution layer while SplitSettle manages the surrounding settlement and recovery state.

### Important

This project uses **Razorpay Test Mode**.

No real production money is intended to be transferred through the hackathon demo.

---

# 📜 Audit Trail

Financial workflows need visibility.

SplitSettle records important system actions in an audit trail.

Examples include:

- Expense creation
- Receipt parsing
- Settlement recomputation
- Payment-link creation
- Recovery actions
- Reminder generation
- Payment-state changes
- Partial-payment updates

The audit trail helps answer:

> **What happened to this obligation?**

Instead of having an invisible state transition, the system provides a history of the important actions that led to the current settlement state.

---

# 📊 Metrics Dashboard

SplitSettle exposes live metrics calculated from the group's actual data.

### Settlement Efficiency

Compares the number of actual optimized transfers against a naive transaction baseline.

```text
Naive transfers
       ↓
Settlement optimization
       ↓
Required transfers
       ↓
Efficiency %
```

### Recovery Rate

Tracks the proportion of settlements currently marked as paid.

### Audit Activity

Shows the number of recorded system actions for the group.

These metrics are calculated from application state rather than being hardcoded presentation values.

---

# 🏗️ System Architecture

```text
                    ┌──────────────────────────┐
                    │          Browser         │
                    │                          │
                    │  Jinja2 UI + Vanilla JS  │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │        FastAPI App        │
                    │                          │
                    │  Group / Expense APIs    │
                    │  Settlement Workflow     │
                    │  Recovery Workflow       │
                    │  Payment Workflow        │
                    └───────┬──────────┬───────┘
                            │          │
              ┌─────────────┘          └──────────────┐
              ▼                                       ▼
    ┌───────────────────┐                   ┌───────────────────┐
    │   Settlement      │                   │     AI Layer      │
    │     Engine        │                   │                   │
    │                   │                   │ Receipt Parsing   │
    │ Net Balances      │                   │ Reminder Writing │
    │ Debt Simplifying  │                   │                   │
    │ Deterministic     │                   │ Anthropic API     │
    └─────────┬─────────┘                   └───────────────────┘
              │
              ▼
    ┌───────────────────┐
    │   SQLModel /      │
    │      SQLite       │
    │                   │
    │ Groups            │
    │ Members           │
    │ Expenses          │
    │ Expense Shares    │
    │ Settlements       │
    │ Audit Logs        │
    └─────────┬─────────┘
              │
              ▼
    ┌───────────────────┐
    │     Razorpay      │
    │                   │
    │  Payment Links    │
    │  Payment Status   │
    │   Test Mode       │
    └───────────────────┘
```

---

# 🔄 End-to-End Workflow

```text
             CREATE GROUP
                  │
                  ▼
            ADD MEMBERS
                  │
                  ▼
          ADD GROUP EXPENSES
                  │
          ┌───────┴────────┐
          │                │
          ▼                ▼
     Manual Entry     AI Receipt Parser
          │                │
          └───────┬────────┘
                  ▼
             EXPENSE LEDGER
                  │
                  ▼
        COMPUTE SETTLEMENT
                  │
                  ▼
        NET BALANCE ENGINE
                  │
                  ▼
        DEBT SIMPLIFICATION
                  │
                  ▼
          REQUIRED TRANSFERS
                  │
                  ▼
        CREATE PAYMENT LINK
                  │
                  ▼
          RAZORPAY PAYMENT
                  │
          ┌───────┴─────────┐
          │                 │
          ▼                 ▼
        PAID            NOT PAID
          │                 │
          │                 ▼
          │          RECOVERY WORKFLOW
          │                 │
          │          ┌──────┴──────┐
          │          ▼             ▼
          │       Reminder      Installment
          │                       /Schedule
          │          │             │
          └──────────┴─────────────┘
                     ▼
              SETTLEMENT CLOSED
                     │
                     ▼
                AUDIT TRAIL
```

---

# ⚙️ Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python |
| Web Framework | FastAPI |
| Templates | Jinja2 |
| Frontend | HTML, CSS, Vanilla JavaScript |
| Database | SQLite |
| ORM / Models | SQLModel |
| AI | Anthropic API |
| AI Model | Claude Sonnet |
| Payments | Razorpay Payment Links |
| Server | Uvicorn |
| Deployment | Render |
| Version Control | Git + GitHub |

---

# 📁 Project Structure

```text
splitsettle-ai/
│
├── app/
│   ├── main.py
│   │   └── FastAPI routes and application logic
│   │
│   ├── models.py
│   │   └── SQLModel database models
│   │
│   ├── database.py
│   │   └── Database engine and sessions
│   │
│   ├── settlement.py
│   │   └── Net balance calculation and debt simplification
│   │
│   ├── ai_agent.py
│   │   └── Receipt parsing and recovery assistance
│   │
│   └── razorpay_client.py
│       └── Razorpay Payment Link integration
│
├── templates/
│   ├── base.html
│   ├── home.html
│   └── group.html
│
├── static/
│   └── style.css
│
├── migrate.py
│   └── Database migration utilities
│
├── seed.py
│   └── Optional demo data
│
├── requirements.txt
│   └── Python dependencies
│
├── .gitignore
│   └── Environment files and local artifacts
│
└── README.md
```

---

# 💻 Running Locally

## 1. Clone the repository

```bash
git clone https://github.com/sathwiko7/splitsettle-ai.git
cd splitsettle-ai
```

---

## 2. Create a virtual environment

### Windows

```powershell
python -m venv venv
venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure environment variables

Create a local `.env` file.

```env
ANTHROPIC_API_KEY=your_anthropic_key

RAZORPAY_KEY_ID=your_razorpay_test_key_id
RAZORPAY_KEY_SECRET=your_razorpay_test_key_secret
```

### Never commit `.env`

API keys and secrets should remain outside source control.

The repository's `.gitignore` is configured to exclude `.env`.

---

# ▶️ Start the Application

Run:

```bash
uvicorn app.main:app --reload
```

The application will be available at:

```text
http://localhost:8000
```

---

# 🌱 Optional Demo Data

The repository contains a `seed.py` script for creating demo data.

Run:

```bash
python seed.py
```

Then start the application:

```bash
uvicorn app.main:app --reload
```

---

# 🧪 AI Fallback Mode

SplitSettle is designed so that the core application can still demonstrate its workflow when external AI credentials are unavailable.

If the Anthropic API key is not configured, the AI-related functionality can fall back to deterministic rule-based behavior.

This means:

```text
No AI API key
     ↓
Core application still runs
     ↓
Settlement logic still works
     ↓
Payment workflow can still be demonstrated
```

The LLM is therefore an enhancement to the workflow rather than a single point of failure for the entire application.

---

# 🧪 Razorpay Test Mode

For real Razorpay test-mode Payment Links, configure:

```env
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
```

The application uses Razorpay's test environment.

If Razorpay credentials are unavailable, the application can fall back to a mock payment-link flow so the surrounding settlement workflow can still be demonstrated.

---

# ☁️ Deployment on Render

SplitSettle AI is deployed as a Python Web Service on Render.

### Build Command

```bash
pip install -r requirements.txt
```

### Start Command

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Environment Variables

Configure these in the Render dashboard:

```text
ANTHROPIC_API_KEY
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
```

Do not place secret values directly inside the source code.

---

# 🔐 Security Considerations

SplitSettle AI follows several important boundaries:

### API keys

Secrets are stored through environment variables rather than source code.

### Payment execution

The system creates payment requests but does not autonomously move money.

The actual payment remains gated by the user completing the Razorpay-hosted payment flow.

### AI boundaries

The AI layer does not determine the correctness-critical financial settlement calculations.

### Auditability

Important system actions are recorded so the settlement history can be inspected.

### Test environment

The hackathon payment integration uses Razorpay Test Mode rather than production payment credentials.

---

# ⚠️ Current Limitations

SplitSettle AI is a hackathon prototype and has intentionally bounded scope.

### Database persistence

The current application uses SQLite.

For a production deployment, a managed relational database such as PostgreSQL would be more appropriate.

### Reminder delivery

The current recovery workflow focuses on generating and tracking reminders inside the application.

Production delivery channels such as WhatsApp, SMS, or email can be added later.

### Payment environment

Razorpay integration is currently demonstrated through Test Mode.

### Authentication

The current hackathon version focuses on the settlement workflow rather than a complete multi-tenant authentication and authorization system.

### Recovery automation

The recovery agent is deliberately bounded and does not autonomously perform unrestricted financial actions.

---

# 🔮 Future Roadmap

Potential future improvements include:

### Payments

- UPI deep links
- Broader payment-method support
- Production Razorpay integration
- Webhook-driven payment updates

### Recovery

- WhatsApp reminders
- Email reminders
- SMS reminders
- Smarter reminder timing
- User-configurable recovery policies

### Intelligence

- Receipt image upload
- OCR pipeline
- Better receipt normalization
- Spending pattern analysis
- Personalized recovery recommendations

### Group Analytics

- Spending categories
- Monthly group analytics
- Individual spending insights
- Recurring expenses
- Budget tracking

### Infrastructure

- PostgreSQL
- Authentication
- Multi-tenant architecture
- Background workers
- Production observability
- Automated testing and CI/CD

---

# 🏆 Why This Is More Than a Bill-Splitting App

Traditional expense splitting answers:

> **"Who owes whom?"**

SplitSettle AI asks a bigger question:

> **"How do we get the group from an outstanding obligation to a completed settlement?"**

That creates a different product loop:

```text
Expense
   ↓
Understand
   ↓
Calculate
   ↓
Optimize
   ↓
Request Payment
   ↓
Recover
   ↓
Track
   ↓
Settle
```

The project combines:

- Deterministic financial computation
- AI-powered unstructured-data understanding
- AI-assisted communication
- Payment infrastructure
- Recovery workflows
- Partial-payment tracking
- Auditability

The central idea is:

> **Don't stop when the bill is split. Close the loop.**

---

# 🎯 Buildathon Positioning

**SplitSettle AI** was built for the **Razorpay AI Buildathon 2026 — Open Track**.

The project focuses on applying AI to a practical financial workflow where AI can provide useful interpretation and communication while deterministic software handles correctness-critical financial operations.

### Core principle

```text
AI for interpretation
+
Algorithms for correctness
+
Razorpay for payment execution
+
Audit logs for accountability
```

---

# 📈 Evidence and Metrics

SplitSettle reports metrics from the current application state rather than presenting fixed numbers.

### Settlement efficiency

The debt simplification algorithm reduces unnecessary transfers compared with a naive pairwise settlement approach.

### Recovery rate

The dashboard calculates the proportion of current settlements marked as paid.

### Audit activity

The system exposes the number of logged actions associated with the group.

These metrics are intended to make the workflow observable rather than relying only on claims in a presentation.

> **Important:** Recovery metrics should be interpreted carefully when using synthetic/demo data. A demo recovery rate is not evidence of real-world adoption.

---

# 🎥 Demo Flow

The recommended product flow is:

```text
1. Create a group
        ↓
2. Add members
        ↓
3. Add expenses
        ↓
4. Use AI receipt extraction
        ↓
5. Add extracted expense to ledger
        ↓
6. Recompute settlement
        ↓
7. View optimized transfers
        ↓
8. Create Razorpay payment link
        ↓
9. Track payment state
        ↓
10. Trigger recovery workflow
        ↓
11. Demonstrate partial payment
        ↓
12. Inspect audit trail
```

---

# 📌 Quick Links

| Resource | Link |
|---|---|
| 🌐 Live Demo | https://splitsettle-ai-5622.onrender.com |
| 🎥 Demo Video | https://youtu.be/IKn3-EWvbEQ |
| 💻 GitHub Repository | https://github.com/sathwiko7/splitsettle-ai |

---

# 👨‍💻 Project

**SplitSettle AI**

Built for:

**Razorpay AI Buildathon 2026 — Open Track**

---

# 📜 License

This project is intended as a hackathon prototype and demonstration.

Add an appropriate open-source license before treating the repository as a production open-source project.

---

## ⭐ Final Thought

> **Splitting isn't the problem. Settling is.**

**SplitSettle AI — from shared expense to completed settlement.**