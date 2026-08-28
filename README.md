# RecoverAI - AI Revenue Recovery Agent

> **AI recommends. Policies decide. Executor acts. Verification
> confirms.**

RecoverAI is an AI-assisted revenue recovery control center designed to
detect failed payments, diagnose recovery opportunities, apply
deterministic safety guardrails, execute eligible recovery actions,
verify outcomes, and maintain a persistent audit trail.

The project is designed for the Razorpay buildathon and supports both a
deterministic **Simulation/Mock mode** for reliable demonstrations and
an optional **Razorpay Test Mode** integration for gateway-state
verification and authorized-payment capture.

------------------------------------------------------------------------

## Product Overview

Failed payments represent potentially recoverable revenue, but automated
payment recovery must be controlled carefully.

RecoverAI separates intelligence from execution:

``` text
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

The AI does **not** have unrestricted authority over payments.

### Core principle

**AI recommends → Policies decide → Executor acts → Verification
confirms**

------------------------------------------------------------------------

## Key Capabilities

-   Failed-payment detection and classification
-   Deterministic recovery rules
-   AI-assisted analysis for ambiguous failures
-   Structured AI decision validation
-   Safety guardrails and policy ceilings
-   High-value transaction protection
-   Refund-request protection
-   Communication opt-out protection
-   Retry/cooldown controls
-   Persistent idempotency protection
-   Recovery state-machine enforcement
-   Payment execution and post-action verification
-   Razorpay Test Mode integration
-   Mock/Simulation payment provider
-   Persistent audit trail
-   Recovery dashboard and revenue-at-risk analytics
-   Evaluation of Rules-only vs AI-assisted recovery
-   Eight deterministic demo scenarios

------------------------------------------------------------------------

## Architecture

``` text
                         ┌──────────────────────┐
                         │      React/Vite      │
                         │    RecoverAI UI      │
                         └──────────┬───────────┘
                                    │
                                    │ /api/*
                                    ▼
                         ┌──────────────────────┐
                         │       FastAPI        │
                         │     Application      │
                         └──────────┬───────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
                 ▼                  ▼                  ▼
          Recovery Engine      AI / Rules         Database
                 │                  │             SQLite/
                 │                  │             SQLAlchemy
                 ▼                  ▼
             Guardrails        Decision
                 │              Validation
                 └──────────────┬───────────────────┘
                                ▼
                         Payment Provider
                         ┌──────┴───────┐
                         │              │
                         ▼              ▼
                       Mock       Razorpay Test
                     Provider         API
                         │              │
                         └──────┬───────┘
                                ▼
                           Verification
                                │
                                ▼
                          Audit / Metrics
```

------------------------------------------------------------------------

## Technology Stack

### Backend

-   Python
-   FastAPI
-   SQLAlchemy
-   Pydantic
-   SQLite

### Frontend

-   React
-   TypeScript
-   Vite

### Integration

-   Razorpay REST APIs
-   Razorpay Test Mode
-   Mock payment provider for deterministic demos

### Evaluation

-   Synthetic payment dataset
-   Held-out evaluation set
-   Rules-only vs AI-assisted benchmark
-   Precision, Recall, F1 and recovered-revenue measurements

### Deployment

-   Docker
-   Docker Compose
-   Compatible with container-based hosting such as Render or Google
    Cloud Run

------------------------------------------------------------------------

# Project Structure

``` text
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
│   │   │   ├── ...
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
├── README.md
└── DEPLOYMENT.md
```

------------------------------------------------------------------------

# Requirements

For local development, install:

-   Python 3.10+ recommended
-   Node.js 18+ recommended
-   npm
-   Git

For Docker deployment/development:

-   Docker Desktop

For Razorpay Test Mode:

-   Razorpay account
-   Razorpay Test Mode API credentials

For an external AI provider, install/configure only the provider
credentials specified by the current `.env.example` and application
configuration.

------------------------------------------------------------------------

# Quick Start --- Local Development

## 1. Clone the repository

``` bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd RecoverAI
```

------------------------------------------------------------------------

## 2. Create a Python virtual environment

### Windows

``` powershell
python -m venv .venv
.venv\Scripts\activate
```

### macOS/Linux

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

------------------------------------------------------------------------

## 3. Install backend dependencies

If the repository contains `requirements.txt`:

``` bash
pip install -r requirements.txt
```

If dependencies are defined elsewhere, follow the project's current
dependency configuration.

------------------------------------------------------------------------

## 4. Install frontend dependencies

``` bash
cd frontend
npm install
cd ..
```

------------------------------------------------------------------------

# Environment Configuration

Create a local `.env` file in the project root.

Start with Simulation mode:

``` env
RAZORPAY_MODE=mock
```

For Razorpay Test Mode:

``` env
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxx
```

Use the project's `.env.example` as the authoritative list of additional
variables.

### Never commit secrets

Do not commit:

``` text
.env
```

or real:

``` text
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
AI provider API keys
database credentials
```

API credentials must remain server-side and must never be embedded in
React/Vite frontend code.

------------------------------------------------------------------------

# Run the Backend

From the repository root:

``` bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Backend:

``` text
http://localhost:8000
```

If the application exposes interactive API documentation, it is normally
available through the FastAPI documentation routes configured by the
application.

------------------------------------------------------------------------

# Run the Frontend

In a second terminal:

``` bash
cd frontend
npm run dev
```

The Vite development server is typically available at:

``` text
http://localhost:5173
```

Use the frontend development URL when developing the UI.

For production/demo deployment, use the compiled frontend served by the
production application/container as configured by the project.

------------------------------------------------------------------------

# Simulation Mode

Simulation mode is recommended for demos because it provides
deterministic scenarios without requiring real gateway credentials.

Set:

``` env
RAZORPAY_MODE=mock
```

The application should display:

``` text
● SIMULATION
```

The simulation supports the project's recovery and safety scenarios
without processing real payments.

------------------------------------------------------------------------

# Razorpay Test Mode

RecoverAI can optionally connect to Razorpay Test Mode.

Set:

``` env
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxx
```

The application communicates with Razorpay server-side.

The test adapter uses the Razorpay API for supported gateway operations
such as:

-   payment retrieval
-   order-payment inspection
-   authorized-payment capture
-   post-action verification

### Important payment-safety behavior

RecoverAI does **not** treat a failed Razorpay payment as directly
capturable.

The real test-mode execution flow is:

``` text
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

------------------------------------------------------------------------

# Integration Status

The application exposes an integration status endpoint:

``` http
GET /api/integrations/razorpay/status
```

The UI uses this to communicate the active provider/environment.

Typical modes:

``` text
SIMULATION
RAZORPAY TEST
```

Credentials are not returned by the status API.

------------------------------------------------------------------------

# Recovery Safety Model

RecoverAI intentionally separates AI decision-making from execution
authority.

## AI

The AI can recommend an action based on available payment/customer
context.

## Policies

Deterministic guardrails decide whether the recommendation is allowed.

## Executor

Only an approved action can reach the payment-provider execution layer.

## Verification

The system verifies the resulting payment state before declaring
success.

This prevents an AI recommendation from becoming an unchecked payment
operation.

------------------------------------------------------------------------

# Guardrails

The system includes protection for scenarios such as:

-   refund requested
-   high-value transactions
-   retry limits
-   cooldowns
-   communication opt-out
-   low-confidence AI decisions
-   unsupported actions
-   duplicate execution
-   already-completed payments
-   unknown gateway states

Guardrails are deterministic and are not overridden by AI output.

------------------------------------------------------------------------

# Persistent Idempotency

RecoverAI maintains its own persistent idempotency mechanism.

Conceptually:

``` text
Request
   ↓
Idempotency Key
   ↓
Database Lookup
   ↓
Already Processed?
 ┌──────┴──────┐
YES           NO
 │             │
 ▼             ▼
Return       Execute
Cached       Action
Result          │
                ▼
             Persist
             Result
```

The idempotency record survives a new database session/process,
preventing duplicate execution after a restart.

Razorpay Capture should not be described as using an unsupported custom
idempotency header. RecoverAI's own persistence layer provides the
application-level protection.

------------------------------------------------------------------------

# Recovery State Machine

The recovery lifecycle follows explicit states.

Conceptually:

``` text
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

Alternative outcomes include escalation, retry-pending and
failure/unknown states according to the implemented state machine.

Invalid transitions are rejected by the backend.

------------------------------------------------------------------------

# Demo Scenarios

RecoverAI includes eight demonstration scenarios:

1.  Successful Recovery
2.  Provider Timeout
3.  High-Value Transaction Block
4.  Refund Protection
5.  Duplicate / Idempotency Protection
6.  Already Completed Payment
7.  AI Unavailable
8.  Malformed AI Output

The demo scenarios are intended to demonstrate both recovery capability
and safe failure handling.

------------------------------------------------------------------------

# Evaluation

The project includes a synthetic dataset and a held-out evaluation
workflow.

The evaluation compares:

``` text
Rules-only
vs
AI-assisted
```

using metrics including:

-   Precision
-   Recall
-   F1 Score
-   Revenue Recovered

The held-out dataset is intended to remain separate from mutable
application/demo state.

### Evaluation integrity

Do not run evaluation against a database state that has been mutated by
demo/reset operations if those operations alter fields used to make the
original ground-truth labels.

In particular, evaluation ground truth must remain consistent with the
generated held-out dataset.

Run:

``` bash
python evaluation/evaluate.py
```

Results are written according to the project's evaluation
implementation, including:

``` text
results/final_results.json
```

Do not hardcode evaluation numbers into the dashboard.

------------------------------------------------------------------------

# Testing

Run the backend test suite:

``` bash
python -m pytest backend/tests/ -v
```

The current verified project baseline is:

``` text
28 passed
0 warnings
```

If tests fail after a change, investigate the regression before
deployment.

------------------------------------------------------------------------

# Production Build

The production application is designed to package the frontend and
backend together using Docker.

The intended production architecture is:

``` text
Public HTTPS URL
       ↓
Docker Container
       ↓
FastAPI
       ↓
Compiled React/Vite frontend
       +
Backend APIs
       ↓
SQLite / Recovery Engine
       ↓
Mock or Razorpay Test Provider
```

The deployed application should not require the Vite development server.

------------------------------------------------------------------------

# Docker

## Build

From the project root:

``` bash
docker build -t recoverai .
```

## Run

Use the port configured by the project's Dockerfile.

A typical local configuration is:

``` bash
docker run --rm -p 8000:8000 -e RAZORPAY_MODE=mock recoverai
```

Then open:

``` text
http://localhost:8000
```

If the Dockerfile uses a different internal port, use that port instead.

------------------------------------------------------------------------

# Docker Compose

If the project uses the supplied Compose configuration:

``` bash
docker compose up --build
```

To stop:

``` bash
docker compose down
```

Use Docker Compose for local containerized verification when
appropriate.

------------------------------------------------------------------------

# Deployment

For a hackathon demonstration, the recommended architecture is a single
containerized web service:

``` text
GitHub
   ↓
Container Build
   ↓
Cloud Web Service
   ↓
RecoverAI
```

Suitable container platforms include:

-   Render
-   Google Cloud Run
-   other Docker-compatible hosting providers

For the simplest public demo, deploy the existing Dockerfile as one web
service.

------------------------------------------------------------------------

# Deployment Environment

For the public hackathon demo, Simulation mode is recommended:

``` env
RAZORPAY_MODE=mock
```

This provides deterministic demo behavior.

Razorpay Test Mode can be enabled separately when gateway integration
needs to be demonstrated:

``` env
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=...
RAZORPAY_KEY_SECRET=...
```

Do not enable live/production payment processing for the hackathon
application.

------------------------------------------------------------------------

# Database Considerations

The current application uses SQLite.

For a public deployment, ensure the SQLite database is stored on
persistent storage if the hosting platform uses ephemeral filesystems.

The application should not reset or reseed the production/demo database
on every application restart.

For a future multi-merchant production SaaS, PostgreSQL or another
managed relational database would be a more appropriate persistence
layer.

------------------------------------------------------------------------

# Security Notes

Before deployment:

-   Keep secrets in the hosting provider's secret/environment-variable
    manager.
-   Never commit `.env`.
-   Never expose Razorpay credentials to the browser.
-   Never put secret keys in Vite environment variables intended for
    client-side use.
-   Do not enable Razorpay Live Mode.
-   Do not expose internal stack traces in production.
-   Keep recovery guardrails server-side.
-   Preserve persistent idempotency.
-   Treat AI output as untrusted input and validate it before execution.

------------------------------------------------------------------------

# Frontend Product Experience

The application intentionally avoids a login barrier for the hackathon
demo.

The intended first-time experience is:

``` text
Open public URL
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

The interface clearly identifies whether the active environment is
Simulation or Razorpay Test Mode.

------------------------------------------------------------------------

# Troubleshooting

## Docker is not recognized on Windows

Install Docker Desktop and restart the terminal after installation.

Verify:

``` bash
docker --version
```

Then:

``` bash
docker compose version
```

------------------------------------------------------------------------

## Frontend cannot reach the backend

Check that:

-   FastAPI is running
-   the Vite proxy configuration is correct for development
-   production builds use same-origin `/api/...` requests
-   no hardcoded `localhost` URL remains in the production frontend

------------------------------------------------------------------------

## Razorpay Test Mode says credentials are missing

Verify:

``` env
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
```

Make sure the credentials are configured on the backend/server
environment.

Restart the application after changing environment variables.

------------------------------------------------------------------------

## Dashboard is empty after deployment

Check:

1.  Database initialization
2.  Seed/demo data
3.  Persistent database storage
4.  API response in the browser Network tab
5.  Backend logs

Do not solve an empty dashboard by hardcoding values into the frontend.

------------------------------------------------------------------------

## Evaluation numbers changed unexpectedly

Check whether the application database was reset or mutated before
evaluation.

Run evaluation against the intended generated held-out dataset and
preserve its ground-truth fields.

------------------------------------------------------------------------

# Demo Checklist

Before presenting RecoverAI:

### Application

-   [ ] Public URL opens successfully
-   [ ] Dashboard loads
-   [ ] Provider indicator is correct
-   [ ] No browser console errors
-   [ ] No failed API requests

### Recovery

-   [ ] Failed payment can be inspected
-   [ ] AI/rules decision is visible
-   [ ] Guardrails are visible
-   [ ] Execution result is visible
-   [ ] Verification result is visible
-   [ ] Audit trail records the operation

### Safety

-   [ ] High-value transaction is blocked/escalated
-   [ ] Refund protection works
-   [ ] Duplicate/idempotency scenario works
-   [ ] Already-completed payment is not executed again
-   [ ] Provider timeout is handled safely

### Evaluation

-   [ ] Evaluation data is real
-   [ ] Rules vs AI comparison is visible
-   [ ] No fabricated metrics

### Environment

-   [ ] Simulation/Test status is clearly visible
-   [ ] No secrets are exposed
-   [ ] No Razorpay Live Mode is enabled

------------------------------------------------------------------------

# Current Verification Baseline

The project has been reported as:

``` text
Backend tests:        28/28 passed
Warnings:             0
Razorpay Test Mode:   Implemented
Simulation Mode:      Implemented
Persistent Idempotency: Implemented
Guardrails:           Implemented
Audit Trail:          Implemented
Evaluation:           Implemented
Demo Scenarios:       8
```

Always rerun the tests after making changes rather than relying solely
on this historical baseline.

------------------------------------------------------------------------

# Design Philosophy

RecoverAI is intentionally not presented as an unrestricted autonomous
payment agent.

The system is built around controlled automation:

> **AI recommends. Policies decide. Executor acts. Verification
> confirms.**

This separation allows RecoverAI to use AI where judgment is useful
while keeping financial execution constrained by deterministic policies,
state validation, idempotency, and post-action verification.

------------------------------------------------------------------------

## License

Add the project's chosen license here before public distribution.

## Acknowledgements

Built as part of the Razorpay AI buildathon.

Razorpay APIs are used only where supported by Razorpay's documented
Test Mode capabilities. Simulation scenarios are provided by RecoverAI's
own mock provider.
