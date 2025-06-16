# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libgl1-mesa-glx \
    libglib2.0-0 \
    ffmpeg \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install -r requirements.txt

# Copy the application code
COPY . .

# Set Python path
ENV PYTHONPATH=/app

# Expose the ports
EXPOSE 8000
EXPOSE 40000-40100/udp

# Command to run the application
CMD ["uvicorn", "examples.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
