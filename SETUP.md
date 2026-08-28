# RecoverAI --- Setup & Deployment Guide

This guide takes a new developer from a clean machine to a working
RecoverAI instance.

------------------------------------------------------------------------

## 1. Prerequisites

Install:

-   Git
-   Python 3.10+
-   Node.js 18+
-   npm

For Docker:

-   Docker Desktop

For Razorpay Test Mode:

-   Razorpay account with Test Mode API credentials

------------------------------------------------------------------------

# 2. Get the Source Code

``` bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd RecoverAI
```

------------------------------------------------------------------------

# 3. Windows Setup

## Check Python

``` powershell
python --version
```

If `python` is unavailable, install Python and ensure it is added to
PATH.

## Check Node.js

``` powershell
node --version
npm --version
```

## Check Docker

``` powershell
docker --version
docker compose version
```

If Windows reports:

``` text
'docker' is not recognized as an internal or external command
```

install Docker Desktop, restart the terminal, and run the commands
again.

------------------------------------------------------------------------

# 4. Backend Setup

Create a virtual environment:

``` powershell
python -m venv .venv
```

Activate it:

``` powershell
.venv\Scripts\activate
```

Install dependencies:

``` powershell
pip install -r requirements.txt
```

If the repository uses a different dependency file, follow that file
instead.

------------------------------------------------------------------------

# 5. Frontend Setup

``` powershell
cd frontend
npm install
cd ..
```

------------------------------------------------------------------------

# 6. Environment Variables

Copy the example environment file:

``` powershell
copy .env.example .env
```

Start with Simulation Mode:

``` env
RAZORPAY_MODE=mock
```

This is the recommended configuration for development and hackathon
demos.

For Razorpay Test Mode:

``` env
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxx
```

Use `.env.example` and `backend/app/config.py` to identify any
additional variables required by the current project.

Never commit `.env`.

------------------------------------------------------------------------

# 7. Initialize Demo Data

Use the project's existing data-generation/seed workflow.

If a fresh database needs to be generated, inspect:

``` text
data/generate_data.py
```

Do not repeatedly reset a working demo database unless you intentionally
want to restore the demo state.

Be especially careful with evaluation data because mutable database
reset operations must not alter the ground truth used by the held-out
evaluation.

------------------------------------------------------------------------

# 8. Start Backend

From the repository root:

``` powershell
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Expected backend:

``` text
http://localhost:8000
```

Keep this terminal running.

------------------------------------------------------------------------

# 9. Start Frontend

Open another terminal:

``` powershell
cd frontend
npm run dev
```

Open:

``` text
http://localhost:5173
```

The frontend should use the configured Vite development proxy to
communicate with the backend.

------------------------------------------------------------------------

# 10. Verify Integration Status

Open the application and verify that the header displays:

``` text
● SIMULATION
```

when:

``` env
RAZORPAY_MODE=mock
```

For Test Mode:

``` env
RAZORPAY_MODE=test
```

the header should display:

``` text
● RAZORPAY TEST
```

No API secret should ever appear in the browser.

------------------------------------------------------------------------

# 11. Verify the Backend

Run:

``` powershell
python -m pytest backend/tests/ -v
```

Expected current baseline:

``` text
28 passed
0 warnings
```

If tests fail, stop and investigate the failure before deployment.

------------------------------------------------------------------------

# 12. Run Evaluation

Run:

``` powershell
python evaluation/evaluate.py
```

Check:

``` text
results/final_results.json
```

Do not edit evaluation results manually.

Do not run evaluation after mutating the held-out dataset.

------------------------------------------------------------------------

# 13. Docker Setup

Build:

``` powershell
docker build -t recoverai .
```

Run:

``` powershell
docker run --rm -p 8000:8000 -e RAZORPAY_MODE=mock recoverai
```

Open:

``` text
http://localhost:8000
```

If the Dockerfile uses a different internal port, follow the port
exposed by the Dockerfile.

------------------------------------------------------------------------

# 14. Docker Compose

If using the repository's Compose configuration:

``` powershell
docker compose up --build
```

Stop:

``` powershell
docker compose down
```

------------------------------------------------------------------------

# 15. Razorpay Test Mode Setup

Razorpay Test Mode is optional.

Create Test Mode API credentials in the Razorpay Dashboard.

Configure them only in the backend environment:

``` env
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxx
```

Restart the backend after changing `.env`.

RecoverAI's server-side adapter uses Basic Authentication for Razorpay
API requests.

The frontend never receives the secret.

------------------------------------------------------------------------

# 16. Understanding Test Mode

RecoverAI does not claim that Razorpay exposes a generic failed-payment
retry API.

For real Razorpay Test Mode, the application validates gateway state
before attempting supported operations.

A failed payment is not directly captured.

An authorized payment may be captured after validation and then
verified.

Already-captured payments are skipped.

Unknown states are escalated.

For deterministic demonstrations such as timeout, malformed AI output,
or duplicate execution, use Simulation Mode.

------------------------------------------------------------------------

# 17. Production Deployment

Recommended hackathon architecture:

``` text
GitHub
   ↓
Docker Build
   ↓
Cloud Web Service
   ↓
RecoverAI
```

A single container is recommended because the application can package
the FastAPI backend and compiled React frontend together.

Suitable platforms include:

-   Render
-   Google Cloud Run
-   another Docker-compatible service

------------------------------------------------------------------------

# 18. Render Deployment

General flow:

1.  Push the project to GitHub.
2.  Create a Render Web Service.
3.  Connect the GitHub repository.
4.  Select Docker-based deployment using the repository Dockerfile.
5.  Configure environment variables.
6.  Deploy.
7.  Open the generated HTTPS URL.
8.  Run the full browser/demo checklist.

Recommended hackathon environment:

``` env
RAZORPAY_MODE=mock
```

Optional Test Mode:

``` env
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=...
RAZORPAY_KEY_SECRET=...
```

If SQLite is used in the deployed service, configure persistent storage
according to the hosting platform's filesystem model.

------------------------------------------------------------------------

# 19. Production Configuration Requirements

The production container should:

-   listen on `0.0.0.0`
-   use the platform-provided port where required
-   serve the compiled React application
-   expose backend `/api/...` routes
-   avoid development-only Vite serving
-   keep secrets server-side
-   avoid debug mode
-   avoid automatic database reset
-   preserve persistent database storage

------------------------------------------------------------------------

# 20. Pre-Submission Test

Before sharing the public URL, verify:

### Dashboard

-   Overview loads
-   Revenue at Risk loads
-   KPI definitions are understandable
-   Recovery Rate formula is available
-   charts are based on real data

### Recovery

-   payment detail loads
-   AI/rules decision appears
-   guardrails appear
-   execution is visible
-   verification is visible

### Safety

-   high-value block
-   refund protection
-   idempotency
-   already-completed payment
-   provider timeout
-   AI unavailable
-   malformed AI output

### Audit

-   audit events appear
-   event details are correct
-   no secrets are exposed

### Evaluation

-   Rules vs AI comparison loads
-   metrics are real
-   pending state is shown when data is unavailable

### Environment

-   Simulation/Test badge is correct
-   no Live mode is shown
-   no credentials appear in frontend/network payloads

------------------------------------------------------------------------

# 21. Common Problems

## `docker` is not recognized

Install Docker Desktop and restart your terminal.

## `npm` is not recognized

Install Node.js and restart your terminal.

## Python import errors

Make sure the virtual environment is active and dependencies are
installed:

``` powershell
.venv\Scripts\activate
pip install -r requirements.txt
```

## Port 8000 is already in use

Find the process using the port or start the backend on another local
port.

If changing the backend port, also update the development frontend proxy
configuration if required.

## Dashboard shows no data

Check:

-   database exists
-   seed/data generation has been performed
-   backend is running
-   frontend API requests succeed
-   browser Network tab
-   backend logs

## Razorpay Test Mode authentication fails

Verify:

-   Test Mode is selected in Razorpay
-   `RAZORPAY_MODE=test`
-   Test Key ID is used
-   Test Key Secret is used
-   credentials are configured on the backend
-   backend was restarted after changing environment variables

## Public deployment loses data

Check whether the hosting provider uses an ephemeral filesystem.

SQLite requires persistent storage if data must survive instance
replacement/redeployments.

------------------------------------------------------------------------

# 22. Security Checklist

Before committing:

``` text
.env                         NOT COMMITTED
Razorpay secrets             NOT COMMITTED
AI API keys                  NOT COMMITTED
Database credentials         NOT COMMITTED
Frontend secret variables    NOT USED
```

Before deployment:

``` text
Razorpay Live Mode           DISABLED
Debug mode                   DISABLED
Secrets                      SERVER-SIDE ONLY
Guardrails                   SERVER-SIDE
Idempotency                  PERSISTENT
```

------------------------------------------------------------------------

# 23. Final Demo Flow

For a short hackathon demonstration:

``` text
Overview
   ↓
Revenue at Risk
   ↓
Open failed payment
   ↓
AI diagnosis
   ↓
Guardrail decision
   ↓
Execute recovery
   ↓
Verification
   ↓
Audit Trail
   ↓
Evaluation
```

Then demonstrate one safety scenario:

``` text
High-Value Transaction
        ↓
AI Recommendation
        ↓
Policy Threshold
        ↓
BLOCKED / HUMAN APPROVAL
```

Finish with:

> AI recommends. Policies decide. Executor acts. Verification confirms.

------------------------------------------------------------------------

# 24. Support Information

When reporting a deployment issue, include:

``` text
Operating System:
Python version:
Node version:
Docker version:
RAZORPAY_MODE:
Command executed:
Full error message:
Backend logs:
Browser console error:
```

Avoid sharing API secrets when reporting errors.
