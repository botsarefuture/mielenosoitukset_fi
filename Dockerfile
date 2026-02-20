# Mielenosoitukset.fi Dockerfile

# Stage 1: Builder for wkhtmltopdf
FROM debian:bookworm-slim AS wkhtmltopdf-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: Final application image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install runtime dependencies for wkhtmltopdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libfontconfig1 \
    libfreetype6 \
    libjpeg62-turbo \
    libpng16-16 \
    libx11-6 \
    libxcb1 \
    libxext6 \
    libxrender1 \
    xfonts-75dpi \
    xfonts-base \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*


COPY wkhtmltox_0.12.7-0.20230411.31.dev.024b2b2.bookworm_amd64.deb .
RUN apt install -y --no-install-recommends ./wkhtmltox_0.12.7-0.20230411.31.dev.024b2b2.bookworm_amd64.deb \
    && rm -f ./wkhtmltox_0.12.7-0.20230411.31.dev.024b2b2.bookworm_amd64.deb

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user and set ownership
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose the Flask port
EXPOSE 5002

# Run the application
CMD ["python", "run.py"]
