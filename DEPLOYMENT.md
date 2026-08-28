# RecoverAI — Production Deployment Documentation

RecoverAI is packaged as a single full-stack service containing both the compiled React frontend assets and the FastAPI backend server. It runs as a containerized Docker application.

---

## 1. Local Development Setup

To run the application locally without Docker:

### Backend (FastAPI)
1. Ensure Python 3.12+ is installed.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run database seed & benchmark evaluation:
   ```bash
   python data/generate_data.py
   python evaluation/evaluate.py
   ```
4. Start FastAPI server:
   ```bash
   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Frontend (React/Vite)
1. Navigate to the `frontend/` directory.
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run Vite dev server:
   ```bash
   npm run dev
   ```
4. Open the browser at [http://localhost:5173](http://localhost:5173). API requests are proxied automatically to `http://localhost:8000`.

---

## 2. Production Docker Build

The application compiles frontend assets in a multi-stage Docker build and mounts the compiled `dist/` bundle inside the Python FastAPI static server.

To build the production container locally:
```bash
docker build -t recoverai .
```

---

## 3. Production Docker Run

To run the compiled production Docker image locally:
```bash
docker run --rm -p 8000:8000 \
  -e RAZORPAY_MODE=mock \
  -e PORT=8000 \
  recoverai
```
Once started, the application is accessible on same-origin paths:
* Web Dashboard: [http://localhost:8000/](http://localhost:8000/)
* API Health Check: [http://localhost:8000/health](http://localhost:8000/health)
* Razorpay Integration Status: [http://localhost:8000/api/integrations/razorpay/status](http://localhost:8000/api/integrations/razorpay/status)

---

## 4. Render Web Service Deployment

To deploy RecoverAI on Render:

1. **Create Web Service**: Link your GitHub repository to Render and create a new **Web Service**.
2. **Environment**: Select **Docker** as the runtime environment.
3. **Build & Start**: Render will automatically detect the root `Dockerfile` and execute the build.
4. **Environment Variables**: Configure the following under Environment settings:
   * `DATABASE_URL`: `sqlite:////data/recoverai.db` (for persistence) or `sqlite:///./recoverai.db` (ephemeral).
   * `RAZORPAY_MODE`: `mock` (default) or `test` (Razorpay Test Mode).
   * `FRONTEND_ORIGIN`: Leave blank (same-origin calls are used).
   * `AI_PROVIDER`: `mock`.
   * `PORT`: Render sets this dynamically; FastAPI binds to it automatically.
5. **Persistent Disk (Optional but Recommended)**:
   * To prevent data reset on restarts/deploys, add a persistent disk volume to your service in Render.
   * **Mount Path**: `/data`
   * **Size**: 1 GB is sufficient.
   * Configure `DATABASE_URL=sqlite:////data/recoverai.db` to store the database on the mounted disk.

---

## 5. Environment Variables Configuration

| Variable Name | Required Values | Default | Description |
| :--- | :--- | :--- | :--- |
| `RAZORPAY_MODE` | `mock` / `test` | `mock` | If `test`, server-side Basic Auth against Razorpay is enabled. |
| `RAZORPAY_KEY_ID` | `rzp_test_xxxxxx` | None | Client Key ID for Razorpay Test Mode. |
| `RAZORPAY_KEY_SECRET`| `xxxxxxxxxxxxxxxx` | None | Secret API Key for Razorpay Test Mode. |
| `AI_PROVIDER` | `mock` / `anthropic` | `mock` | AI analysis mode provider. |
| `FRONTEND_ORIGIN` | Comma-separated URLs | None | CORS allowed origins. Default permits localhost. |
| `PORT` | Dynamic integer | `8000` | Port uvicorn binds to inside the container. |

---

## 6. Database Persistence & Seeding

* **Location**: Ephemeral SQLite is stored in `/app/recoverai.db`. Persistent SQLite is stored in `/data/recoverai.db`.
* **Initialization**: FastAPI automatically executes tables creation (`Base.metadata.create_all`) on app startup.
* **Seed Behavior**: If `PaymentRecord` table contains fewer than 1000 records, the startup cmd runs the synthetic seeder. If the database is already seeded, the seeder detects the records and skips immediately, preserving all user/simulation states across process restarts.

---

## 7. Troubleshooting

* **Frontend displays 404 on API calls**: Ensure you run backend and frontend on same-origin paths, or configure `FRONTEND_ORIGIN` if running separated servers.
* **Database Wiped on Deploy**: Ensure you have mounted a persistent volume on Render at `/data` and updated your `DATABASE_URL` to point to `/data/recoverai.db`.
