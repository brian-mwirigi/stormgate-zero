FROM node:20-slim AS ui
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=ui /ui/dist ./frontend/dist
ENV STORMGATE_OFFLINE=1
EXPOSE 7860 8000
CMD ["sh", "-c", "python scripts/generate_demo_assets.py && uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
