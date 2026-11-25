# ========================================================
# Stage 1: Build the React 19 / Vite Frontend
# ========================================================
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

COPY JobRadar/JobRadar/Frontend/package*.json ./
RUN npm ci

COPY JobRadar/JobRadar/Frontend/ ./
RUN npm run build

# ========================================================
# Stage 2: Python Backend & Production Runtime
# ========================================================
FROM python:3.12-slim AS runner

WORKDIR /app

# Install system dependencies for build tools and sqlite
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install backend requirements
COPY JobRadar/JobRadar/DDS-Job-Market-Project/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy Backend application source, database, and models
COPY JobRadar/JobRadar/DDS-Job-Market-Project/ ./backend/
COPY JobRadar/JobRadar/AI_ML/ ./AI_ML/

# Copy compiled frontend distribution from Stage 1 into the expected location
COPY --from=frontend-builder /app/frontend/dist ./Frontend/dist/

# Set Python path to backend src
ENV PYTHONPATH=/app/backend/src
ENV PORT=8000
EXPOSE 8000

# Healthcheck to ensure FastAPI service is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

# Start Uvicorn serving both API and static frontend bundle
CMD ["sh", "-c", "uvicorn job_market.api:app --host 0.0.0.0 --port ${PORT}"]
