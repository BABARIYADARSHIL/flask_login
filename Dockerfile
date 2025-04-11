FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    libboost-all-dev \
    libatlas-base-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libx264-dev \
    pkg-config \
    wget \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir face_recognition opencv-python-headless numpy flask python-dotenv pymongo cloudinary getmac gunicorn

# Copy your app
COPY . /app
WORKDIR /app

# Start the app with Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app"]
