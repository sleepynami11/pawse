# Public demo image (Cloud Run or any container host). Keys come from the host's secret store, never the image.

# The React app in web/, served by FastAPI at /app.
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pawse/ pawse/
COPY research/ research/
COPY --from=web /web/dist web/dist
RUN useradd --create-home pawse
USER pawse
# --proxy-headers: behind an HTTPS proxy the app must see https, or the same-origin POST check rejects every request.
CMD uvicorn pawse.app:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips="*"
