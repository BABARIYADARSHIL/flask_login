# Use a CPU-only TensorFlow base image
FROM tensorflow/tensorflow:2.15.0

# Install required system libraries
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

# Upgrade pip to the latest version
RUN pip install --no-cache-dir --upgrade pip

# Forcefully remove distutils-installed blinker
RUN python -m pip uninstall -y blinker || true
RUN rm -rf /usr/local/lib/python3.11/dist-packages/blinker* || true

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download DeepFace model to avoid runtime download
RUN mkdir -p /root/.deepface/weights && \
    wget -O /root/.deepface/weights/facenet512_weights.h5 \
    https://github.com/serengil/deepface_models/releases/download/v1.0/facenet512_weights.h5

# Copy codebase
COPY . .

# Set environment variables for TensorFlow
ENV TF_CPP_MIN_LOG_LEVEL=3
ENV TF_ENABLE_ONEDNN_OPTS=0

# Start the app with Gunicorn (single worker, multiple threads)
CMD ["gunicorn", "--workers=1", "--threads=4", "--timeout=120", "--bind=0.0.0.0:8000", "app:app"]