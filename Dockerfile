FROM python:3.11-slim

# Install required system libraries (libgl1 helps with opencv-related issues)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    build-essential \
    cmake \
    wget \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your codebase
COPY . .

# Start the app with Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app"]
