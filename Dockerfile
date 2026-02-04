# GovSniper Dockerfile for Railway
# Optimized for WeasyPrint PDF generation

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies for WeasyPrint and document processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    # WeasyPrint dependencies
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libcairo2-dev \
    libffi-dev \
    libgdk-pixbuf2.0-0 \
    libfribidi0 \
    libharfbuzz0b \
    # Fonts
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    # For shared-mime-info (file type detection)
    shared-mime-info \
    # For libmagic (python-magic)
    libmagic1 \
    # For lxml
    libxml2-dev \
    libxslt1-dev \
    # Build tools (temporary)
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f -v

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port (Railway uses PORT env var)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health')" || exit 1

# Run migrations and start the application (Railway sets PORT env var dynamically)
CMD ["sh", "-c", "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
