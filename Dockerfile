# Public demo image (Cloud Run or any container host). Keys come from the host's secret store, never the image.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pawse/ pawse/
COPY research/ research/
RUN useradd --create-home pawse
USER pawse
# --proxy-headers: behind an HTTPS proxy the app must see https, or the same-origin POST check rejects every request.
CMD uvicorn pawse.app:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips="*"
