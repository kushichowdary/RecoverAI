# Stage 1: Build the React frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Serve using Python and FastAPI
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files and generated data
COPY backend/ ./backend/
COPY data/ ./data/
COPY evaluation/ ./evaluation/

# Copy compiled frontend from Stage 1
COPY --from=frontend-builder /app/dist ./frontend/dist

# Expose FastAPI port
EXPOSE 8000

# Set environment variables
ENV DATABASE_URL=sqlite:///./recoverai.db
ENV AI_PROVIDER=mock
ENV RAZORPAY_MODE=mock

# Run database creation, data seed, and start server
CMD ["sh", "-c", "python data/generate_data.py && python evaluation/evaluate.py && uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

