# Builds a production-ready image for the FastAPI backend.
#
# PyTorch is installed CPU-only to keep the image smaller.
# The CLIP model (open_clip) depends on torch at runtime.

FROM python:3.12-slim

# System dependencies required by asyncpg, psycopg2, Pillow, and GeoAlchemy2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgeos-dev \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONPATH=/app

# Install Python dependencies
COPY requirements.txt .

# Install PyTorch CPU-only first (smaller download, no CUDA needed)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install the rest of the requirements
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
