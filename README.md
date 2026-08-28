# RecoverAI — AI Revenue Recovery Agent

> **AI recommends. Policies decide. Executor acts. Verification confirms.**

RecoverAI is an AI-assisted revenue recovery control center designed to detect failed payments, diagnose recovery opportunities, apply deterministic safety guardrails, execute eligible recovery actions, verify outcomes, and maintain a persistent audit trail.

Built for the **Razorpay AI Buildathon 2026**, RecoverAI supports both:

* **Simulation / Mock Mode** — deterministic and safe for demonstrations
* **Razorpay Test Mode** — optional integration for gateway-state verification and authorized-payment capture

> ⚠️ **Important:** This project is a buildathon demonstration. It does not use Razorpay Live Mode or process real customer payments. Simulation scenarios use synthetic/demo data.

---

## Table of Contents

1. [Problem](#problem)
2. [Solution](#solution)
3. [Core Principle](#core-principle)
4. [Key Capabilities](#key-capabilities)
5. [Architecture](#architecture)
6. [How RecoverAI Works](#how-recoverai-works)
7. [Safety & Guardrails](#safety--guardrails)
8. [Persistent Idempotency](#persistent-idempotency)
9. [Recovery State Machine](#recovery-state-machine)
10. [Technology Stack](#technology-stack)
11. [Project Structure](#project-structure)
12. [Requirements](#requirements)
13. [Quick Start](#quick-start)
14. [Environment Configuration](#environment-configuration)
15. [Simulation Mode](#simulation-mode)
16. [Razorpay Test Mode](#razorpay-test-mode)
17. [Integration Status](#integration-status)
18. [Testing](#testing)
19. [Evaluation](#evaluation)
20. [Demo Scenarios](#demo-scenarios)
21. [Docker](#docker)
22. [Docker Compose](#docker-compose)
23. [Production Deployment](#production-deployment)
24. [Database Considerations](#database-considerations)
25. [Security](#security)
26. [Troubleshooting](#troubleshooting)
27. [Demo Flow](#demo-flow)
28. [Pre-Submission Checklist](#pre-submission-checklist)
29. [Limitations](#limitations)
30. [Future Improvements](#future-improvements)
31. [License](#license)
32. [Acknowledgements](#acknowledgements)

---

# Problem

Failed payments represent potentially recoverable revenue, but not every failed payment should be retried or handled in the same way.

A payment can fail because of:

* Temporary provider/network problems
* Authentication issues
* Customer payment-method problems
* Retry limits
* Refund requests
* Already-completed payments
* Other gateway or application states

Treating every failed payment identically can lead to:

* Missed revenue-recovery opportunities
* Unnecessary retries
* Duplicate execution
* Poor customer experience
* Unsafe automated payment operations

The challenge is therefore not simply:

> **"Can AI decide what to do?"**

It is:

> **"Can AI recommend useful recovery actions while deterministic policies prevent unsafe financial operations?"**

---

# Solution

RecoverAI separates **intelligence from execution**.

The system follows this pipeline:

```text
Failed Payment
     ↓
Detection
     ↓
Diagnosis
     ↓
AI / Rules Recommendation
     ↓
Schema Validation
     ↓
Deterministic Guardrails
     ↓
Idempotency Check
     ↓
Execution
     ↓
Gateway / State Verification
     ↓
Recovered / Escalated / Failed
     ↓
Audit Trail
```

The AI does **not** receive unrestricted authority over payment execution.

Instead, AI provides a recommendation, while deterministic application policies determine whether that recommendation is actually allowed.

---

# Core Principle

## AI recommends → Policies decide → Executor acts → Verification confirms

This separation is the central design principle of RecoverAI.

### AI

The AI can analyze available payment and customer context and recommend a recovery action.

### Policies

Deterministic guardrails evaluate whether that recommendation is safe and allowed.

### Executor

Only an approved action can reach the payment-provider execution layer.

### Verification

The system checks the resulting payment state before declaring recovery successful.

This prevents an AI recommendation from becoming an unchecked financial operation.

---

# Key Capabilities

* Failed-payment detection and classification
* Deterministic recovery rules
* AI-assisted analysis for ambiguous failures
* Structured AI decision validation
* Safety guardrails and policy ceilings
* High-value transaction protection
* Refund-request protection
* Communication opt-out protection
* Retry and cooldown controls
* Persistent idempotency protection
* Recovery state-machine enforcement
* Payment execution and post-action verification
* Razorpay Test Mode integration
* Mock / Simulation payment provider
* Persistent audit trail
* Recovery dashboard
* Revenue-at-risk analytics
* Rules-only vs AI-assisted evaluation
* Eight deterministic demonstration scenarios

---

# Architecture

```text
                         ┌──────────────────────┐
                         │      React/Vite      │
                         │     RecoverAI UI     │
                         └──────────┬───────────┘
                                    │
                                    │ /api/*
                                    ▼
                         ┌──────────────────────┐
                         │       FastAPI        │
                         │     Application      │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
             Recovery Engine   AI / Rules       Database
                    │               │          SQLite/
                    │               │          SQLAlchemy
                    ▼               ▼
                Guardrails      Decision
                    │           Validation
                    └──────────────┬────────────┘
                                   ▼
                           Payment Provider
                         ┌─────────┴─────────┐
                         │                   │
                         ▼                   ▼
                       Mock            Razorpay Test
                     Provider               API
                         │                   │
                         └─────────┬─────────┘
                                   ▼
                              Verification
                                   │
                                   ▼
                              Audit / Metrics
```

---

# How RecoverAI Works

## 1. Detect

The system identifies failed or potentially recoverable payments.

## 2. Diagnose

Payment and customer context is analyzed to understand the likely recovery opportunity.

## 3. Recommend

AI and deterministic rules produce a structured recovery recommendation.

## 4. Validate

AI output is treated as untrusted input and validated against the expected schema.

## 5. Apply Guardrails

Deterministic policies determine whether the recommendation is allowed.

## 6. Check Idempotency

The system checks whether the same recovery operation has already been processed.

## 7. Execute

Only an approved operation is sent to the payment provider.

## 8. Verify

The resulting gateway/payment state is checked.

## 9. Record

The operation and its outcome are persisted in the audit trail.

---

# Safety & Guardrails

RecoverAI intentionally keeps financial execution outside the direct control of the AI.

The system includes protections for:

* Refund requests
* High-value transactions
* Retry limits
* Cooldown periods
* Communication opt-outs
* Low-confidence AI decisions
* Unsupported actions
* Duplicate execution
* Already-completed payments
* Unknown gateway states
* Provider timeouts
* AI unavailability
* Malformed AI output

Guardrails are deterministic and **cannot be overridden by AI output**.

This means that even if an AI recommendation is incorrect, the policy layer can block the operation.

---

# Persistent Idempotency

RecoverAI maintains its own persistent application-level idempotency mechanism.

Conceptually:

```text
Request
   ↓
Idempotency Key
   ↓
Database Lookup
   ↓
Already Processed?
   ┌───────────────┴───────────────┐
  YES                             NO
   │                               │
   ▼                               ▼
Return Cached                    Execute
Result                             │
                                   ▼
                                Persist
                                 Result
```

The idempotency record survives a new database session/process.

This helps prevent duplicate execution after an application restart.

> **Note:** Razorpay Capture should not be described as using an unsupported custom idempotency header. RecoverAI's protection is provided by its own persistent application layer.

---

# Recovery State Machine

The recovery lifecycle follows explicit states:

```text
DETECTED
   ↓
ANALYZING
   ↓
DECIDED
   ↓
GUARDRAIL_CHECK
   ↓
APPROVED
   ↓
EXECUTING
   ↓
VERIFYING
   ↓
RECOVERED
```

Alternative outcomes include:

```text
ESCALATED
RETRY_PENDING
FAILED
UNKNOWN
```

Invalid state transitions are rejected by the backend.

---

# Technology Stack

## Backend

* Python
* FastAPI
* SQLAlchemy
* Pydantic
* SQLite

## Frontend

* React
* TypeScript
* Vite

## Payment Integration

* Razorpay REST APIs
* Razorpay Test Mode
* Mock payment provider

## Evaluation

* Synthetic payment dataset
* Held-out evaluation set
* Rules-only vs AI-assisted benchmark
* Precision
* Recall
* F1 Score
* Revenue Recovered

## Deployment

* Docker
* Docker Compose
* Container-compatible hosting such as Render or Google Cloud Run

---

# Project Structure

```text
RecoverAI/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   │
│   │   ├── services/
│   │   │   └── ...
│   │   │
│   │   ├── ai/
│   │   │   └── ai_provider.py
│   │   │
│   │   └── integrations/
│   │       └── payment_adapter.py
│   │
│   └── tests/
│       └── test_recovery.py
│
├── frontend/
│   └── src/
│       └── App.tsx
│
├── data/
│   └── generate_data.py
│
├── evaluation/
│   └── evaluate.py
│
├── results/
│   └── final_results.json
│
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── pytest.ini
└── README.md
```

---

# Requirements

For local development:

* Git
* Python 3.10+
* Node.js 18+
* npm

For Docker:

* Docker Desktop

For Razorpay Test Mode:

* Razorpay account
* Razorpay Test Mode API credentials

For an external AI provider:

* Configure the provider credentials specified by the project's `.env.example` and application configuration.

---

# Quick Start

## 1. Clone the Repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd RecoverAI
```

---

## 2. Create a Python Virtual Environment

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install Backend Dependencies

```bash
pip install -r requirements.txt
```

If the project uses a different dependency configuration, follow the repository's current dependency files.

---

## 4. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

---

# Environment Configuration

Create a local `.env` file in the project root.

The recommended starting configuration is **Simulation Mode**:

```env
RAZORPAY_MODE=mock
```

For Razorpay Test Mode:

```env
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxx
```

Use `.env.example` as the authoritative source for any additional environment variables required by the current application.

## Never Commit Secrets

Do not commit:

```text
.env
```

or real:

```text
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
AI provider API keys
database credentials
```

API credentials must remain server-side and must never be embedded into React/Vite frontend code.

---

# Run the Backend

From the repository root:

```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

The backend should be available at:

```text
http://localhost:8000
```

Keep this terminal running.

If the application exposes FastAPI interactive documentation, it will be available through the documentation routes configured by the application.

---

# Run the Frontend

Open a second terminal.

Activate the virtual environment if necessary, then:

```bash
cd frontend
npm run dev
```

The Vite development server is typically available at:

```text
http://localhost:5173
```

The frontend should communicate with the backend through the configured Vite proxy.

For production deployment, the compiled frontend is served by the production application/container rather than the Vite development server.

---

# Simulation Mode

Simulation Mode is the recommended configuration for development and hackathon demonstrations.

Set:

```env
RAZORPAY_MODE=mock
```

The application should display:

```text
● SIMULATION
```

Simulation Mode provides deterministic recovery scenarios without requiring real gateway credentials or processing real payments.

It is especially useful for demonstrating:

* Successful recovery
* Provider timeout
* High-value blocking
* Refund protection
* Duplicate execution
* Already-completed payments
* AI unavailable
* Malformed AI output

---

# Razorpay Test Mode

RecoverAI can optionally connect to Razorpay Test Mode.

Configure:

```env
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxx
```

The application communicates with Razorpay from the server side.

The Test Mode adapter supports gateway operations such as:

* Payment retrieval
* Order-payment inspection
* Authorized-payment capture
* Post-action verification

## Important Payment-Safety Behavior

RecoverAI does **not** treat a failed Razorpay payment as directly capturable.

The Test Mode execution flow is:

```text
Fetch Payment
      ↓
Inspect Gateway Status
      ↓
Authorized?
   ┌──┴──┐
  YES    NO
   │      │
   ▼      ▼
Verify   Escalate/
Context  Skip
   │
   ▼
Capture
   │
   ▼
Verify Again
   │
   ▼
Captured?
   │
   ▼
RECOVERED
```

Already-captured payments are skipped rather than captured again.

Unknown payment states are escalated.

Restart the backend after changing `.env`.

---

# Integration Status

The application exposes an integration status endpoint:

```http
GET /api/integrations/razorpay/status
```

The UI uses this endpoint to communicate the active provider/environment.

Typical states:

```text
SIMULATION
RAZORPAY TEST
```

Credentials are not returned by the status API.

The frontend should never receive the Razorpay secret.

---

# Testing

Run the backend test suite:

```bash
python -m pytest backend/tests/ -v
```

The current project baseline is:

```text
28 passed
0 warnings
```

Always rerun the tests after making changes rather than relying solely on the historical baseline.

If tests fail after a change, investigate the regression before deployment.

---

# Evaluation

RecoverAI includes a synthetic dataset and a held-out evaluation workflow.

The evaluation compares:

```text
Rules-only
    vs
AI-assisted
```

using metrics including:

* Precision
* Recall
* F1 Score
* Revenue Recovered

Run:

```bash
python evaluation/evaluate.py
```

Results are written to:

```text
results/final_results.json
```

## Evaluation Integrity

The held-out evaluation dataset should remain separate from mutable application/demo state.

Do not run evaluation against a database state that has been modified by demo/reset operations if those operations alter fields used to generate the original ground-truth labels.

Do not manually edit evaluation results.

Do not hardcode evaluation numbers into the dashboard.

---

# Demo Scenarios

RecoverAI includes eight deterministic demonstration scenarios:

1. Successful Recovery
2. Provider Timeout
3. High-Value Transaction Block
4. Refund Protection
5. Duplicate / Idempotency Protection
6. Already Completed Payment
7. AI Unavailable
8. Malformed AI Output

These scenarios demonstrate both:

* Recovery capability
* Safe failure handling

---

# Docker

## Build

From the project root:

```bash
docker build -t recoverai .
```

## Run

A typical local configuration is:

```bash
docker run --rm -p 8000:8000 -e RAZORPAY_MODE=mock recoverai
```

Then open:

```text
http://localhost:8000
```

If the Dockerfile uses a different internal port, use the port configured by the Dockerfile.

---

# Docker Compose

If using the supplied Compose configuration:

```bash
docker compose up --build
```

To stop:

```bash
docker compose down
```

Docker Compose can be used for local containerized verification.

---

# Production Deployment

For a hackathon demonstration, the recommended architecture is a single containerized web service:

```text
GitHub
   ↓
Container Build
   ↓
Cloud Web Service
   ↓
RecoverAI
```

Suitable container platforms include:

* Render
* Google Cloud Run
* Other Docker-compatible hosting providers

For the simplest public demo, deploy the existing Dockerfile as one web service.

---

# Deployment Environment

For the public hackathon demo, use Simulation Mode:

```env
RAZORPAY_MODE=mock
```

This provides deterministic demo behavior.

Razorpay Test Mode can be enabled separately when gateway integration needs to be demonstrated:

```env
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=...
RAZORPAY_KEY_SECRET=...
```

**Do not enable Razorpay Live Mode for the hackathon application.**

---

# Production Container Requirements

The production container should:

* Listen on `0.0.0.0`
* Use the platform-provided port where required
* Serve the compiled React application
* Expose backend `/api/...` routes
* Avoid development-only Vite serving
* Keep secrets server-side
* Avoid debug mode
* Avoid automatic database resets
* Preserve persistent database storage
* Preserve persistent idempotency records

---

# Database Considerations

The current application uses SQLite.

For public deployment, ensure the SQLite database is stored on persistent storage if the hosting platform uses an ephemeral filesystem.

The application should not reset or reseed the production/demo database on every application restart.

For a future multi-merchant production SaaS architecture, PostgreSQL or another managed relational database would be more appropriate.

---

# Security

Before deployment:

* Keep secrets in the hosting provider's secret/environment-variable manager
* Never commit `.env`
* Never expose Razorpay credentials to the browser
* Never put secret keys in Vite environment variables intended for client-side use
* Do not enable Razorpay Live Mode
* Do not expose internal stack traces in production
* Keep recovery guardrails server-side
* Preserve persistent idempotency
* Treat AI output as untrusted input
* Validate AI output before execution

## Security Checklist

```text
.env                         NOT COMMITTED
Razorpay secrets             NOT COMMITTED
AI API keys                  NOT COMMITTED
Database credentials         NOT COMMITTED
Frontend secret variables    NOT USED
```

Before deployment:

```text
Razorpay Live Mode           DISABLED
Debug mode                   DISABLED
Secrets                      SERVER-SIDE ONLY
Guardrails                   SERVER-SIDE
Idempotency                  PERSISTENT
```

---

# Frontend Product Experience

The application intentionally avoids a login barrier for the hackathon demonstration.

The intended first-time experience is:

```text
Open Public URL
      ↓
RecoverAI Dashboard
      ↓
Revenue at Risk
      ↓
Select Payment
      ↓
AI Diagnosis
      ↓
Guardrails
      ↓
Execution
      ↓
Verification
      ↓
Audit Trail
```

The interface clearly identifies whether the active environment is:

```text
SIMULATION
```

or:

```text
RAZORPAY TEST
```

---

# Troubleshooting

## `docker` is not recognized on Windows

If Windows displays:

```text
'docker' is not recognized as an internal or external command
```

install Docker Desktop and restart the terminal.

Verify:

```powershell
docker --version
docker compose version
```

---

## `npm` is not recognized

Install Node.js and restart the terminal.

Verify:

```powershell
node --version
npm --version
```

---

## Python Import Errors

Make sure the virtual environment is active:

```powershell
.venv\Scripts\activate
```

Then install dependencies:

```powershell
pip install -r requirements.txt
```

---

## Port 8000 Is Already in Use

Find the process using port `8000`, stop it, or start the backend on another local port.

If changing the backend port, update the frontend proxy configuration if required.

---

## Frontend Cannot Reach Backend

Check that:

* FastAPI is running
* The Vite proxy configuration is correct
* Production builds use same-origin `/api/...` requests
* No hardcoded `localhost` URL remains in the production frontend
* Browser Network requests are reaching the expected API
* Backend logs show incoming requests

---

## Dashboard Shows No Data

Check:

1. Database initialization
2. Seed/demo data
3. Backend status
4. Frontend API requests
5. Browser Network tab
6. Backend logs
7. Persistent database storage when deployed

Do not solve an empty dashboard by hardcoding values into the frontend.

---

## Razorpay Test Mode Credentials Are Missing

Verify:

```env
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
```

Make sure:

* Test Mode credentials are being used
* Credentials are configured on the backend
* Credentials are not placed in frontend code
* The backend was restarted after changing environment variables

---

## Evaluation Numbers Changed Unexpectedly

Check whether the application database was reset or mutated before evaluation.

Run evaluation against the intended generated held-out dataset and preserve its ground-truth fields.

---

## Public Deployment Loses Data

Check whether the hosting provider uses an ephemeral filesystem.

SQLite requires persistent storage if data must survive:

* Instance replacement
* Redeployment
* Restart
* Scaling events

---

# Demo Flow

For a short hackathon demonstration:

```text
Overview
   ↓
Revenue at Risk
   ↓
Open Failed Payment
   ↓
AI Diagnosis
   ↓
Guardrail Decision
   ↓
Execute Recovery
   ↓
Verification
   ↓
Audit Trail
   ↓
Evaluation
```

Then demonstrate one safety scenario:

```text
High-Value Transaction
        ↓
AI Recommendation
        ↓
Policy Threshold
        ↓
BLOCKED / HUMAN APPROVAL
```

The key message:

> **AI recommends. Policies decide. Executor acts. Verification confirms.**

---

# Pre-Submission Checklist

## Application

* [ ] Public URL opens successfully
* [ ] Dashboard loads
* [ ] Provider indicator is correct
* [ ] No browser console errors
* [ ] No failed API requests

## Recovery

* [ ] Failed payment can be inspected
* [ ] AI/rules decision is visible
* [ ] Guardrails are visible
* [ ] Execution result is visible
* [ ] Verification result is visible
* [ ] Audit trail records the operation

## Safety

* [ ] High-value transaction is blocked/escalated
* [ ] Refund protection works
* [ ] Duplicate/idempotency scenario works
* [ ] Already-completed payment is not executed again
* [ ] Provider timeout is handled safely
* [ ] AI unavailable scenario works
* [ ] Malformed AI output is rejected safely

## Evaluation

* [ ] Evaluation data is separate from mutable demo state
* [ ] Rules vs AI comparison is visible
* [ ] Metrics are generated by the evaluation workflow
* [ ] No fabricated metrics are displayed

## Environment

* [ ] Simulation/Test status is clearly visible
* [ ] No secrets are exposed
* [ ] Razorpay Live Mode is disabled

---

# Current Verification Baseline

The project baseline documented during development is:

```text
Backend tests:          28/28 passed
Warnings:               0
Razorpay Test Mode:     Implemented
Simulation Mode:        Implemented
Persistent Idempotency: Implemented
Guardrails:             Implemented
Audit Trail:            Implemented
Evaluation:             Implemented
Demo Scenarios:         8
```

Always rerun the test suite after making changes.

---

# Limitations

RecoverAI is a buildathon demonstration and has several limitations.

### Synthetic / Demo Data

Simulation scenarios use synthetic/demo data rather than production customer data.

### Test Mode Only

Razorpay integration is intended for Test Mode. Live payment processing is intentionally disabled for the hackathon deployment.

### SQLite

SQLite is suitable for the current demonstration but is not the preferred database architecture for a large multi-merchant production system.

### AI Dependency

AI-assisted analysis depends on the configured external AI provider. The application must safely handle AI unavailability and malformed AI output.

### Recovery Calibration

Demo recovery behavior and evaluation results should not be interpreted as production-calibrated financial predictions.

---

# Future Improvements

Potential future improvements include:

* Multi-merchant architecture
* PostgreSQL-based production persistence
* Real production webhook ingestion
* More advanced recovery policies
* Improved recovery prediction models
* A/B testing of recovery strategies
* Actual recovery-outcome feedback loops
* SMS/WhatsApp recovery communication
* Multi-language customer messaging
* Merchant-specific policies
* Human approval workflows
* Production-grade observability
* Advanced analytics and reporting

---

# Design Philosophy

RecoverAI is intentionally **not** presented as an unrestricted autonomous payment agent.

The system is built around controlled automation:

> **AI recommends. Policies decide. Executor acts. Verification confirms.**

This separation allows AI to be used where judgment is useful while keeping financial execution constrained by:

* Deterministic policies
* Schema validation
* State validation
* Idempotency
* Guardrails
* Post-action verification
* Auditability

---

# Screenshots

Add screenshots of the actual deployed application here before final submission.

Recommended screenshots:

```text
assets/
├── dashboard.png
├── payment-detail.png
├── recovery-center.png
├── guardrails.png
├── audit-trail.png
└── evaluation.png
```

Suggested README presentation:

```markdown
## Dashboard

![RecoverAI Dashboard](assets/dashboard.png)

## Recovery Decision

![Recovery Decision](assets/payment-detail.png)

## Audit Trail

![Audit Trail](assets/audit-trail.png)

## Evaluation

![Evaluation](assets/evaluation.png)
```

---

# License

Add the project's chosen license here before public distribution.

---

# Acknowledgements

Built as part of the **Razorpay AI Buildathon 2026**.

Razorpay APIs are used only where supported by Razorpay's documented Test Mode capabilities. Simulation scenarios are provided by RecoverAI's own mock provider.

---

## Final Demo Message

> **RecoverAI doesn't give AI unrestricted control over payments.**
>
> **AI recommends. Policies decide. Executor acts. Verification confirms.**
