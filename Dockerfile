FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    portaudio19-dev \
    python3-dev \
    ffmpeg \
    default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./
COPY .env.example .env.example
COPY downloads/ ./downloads/

# Create directories for audio output
RUN mkdir -p /app/audio /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYGAME_HIDE_SUPPORT_PROMPT=1

# Expose port for health check (optional)
EXPOSE 8080

# Default command
CMD ["python3", "main.py"]
