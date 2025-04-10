# Base image with Python and system packages
FROM python:3.10-slim

# Install OS-level dependencies for dlib, face_recognition, opencv
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    libboost-python-dev \
    libboost-thread-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy your app code
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port (adjust if needed)
EXPOSE 5000

# Start the Flask app (adjust app filename if needed)
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
