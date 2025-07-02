# Multi-stage build for optimization
FROM python:3.11-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim as runtime

# Security: Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Copy Python dependencies
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application code
WORKDIR /app
COPY --chown=appuser:appuser . .

# Create directories for keys
RUN mkdir -p /keys && chown appuser:appuser /keys

USER appuser
EXPOSE $SERVER_PORT

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${SERVER_PORT:-3600}"]