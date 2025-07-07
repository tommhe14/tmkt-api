FROM python:3.9-slim

WORKDIR /app

# Install system dependencies (optional, but recommended for some Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Install the app in production mode (remove `-e` for production)
RUN pip install --no-cache-dir .

# Run with auto-reload disabled (production mode)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]