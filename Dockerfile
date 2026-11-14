# Container for hosting Gait (for example on Railway). All data the app needs is committed in data/.
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
# Railway sets PORT; 8000 when run elsewhere.
CMD ["sh", "-c", "uvicorn gait.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
