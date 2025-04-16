# Use a CPU-only TensorFlow base image to avoid CUDA dependencies
FROM tensorflow/tensorflow:2.15.0

# Install required system libraries (libgl1 for OpenCV, others for compatibility)
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

# Pre-download DeepFace model to avoid runtime download
RUN python -c "from deepface import DeepFace; DeepFace.detectFace('dummy.jpg', detector_backend='ssd', model_name='Facenet512', enforce_detection=False)" || true

# Copy codebase
COPY . .

# Set environment variables to suppress TensorFlow warnings and optimize memory
ENV TF_CPP_MIN_LOG_LEVEL=3
ENV TF_ENABLE_ONEDNN_OPTS=0

# Start the app with Gunicorn (single worker, multiple threads)
CMD ["gunicorn", "--workers=1", "--threads=4", "--timeout=120", "--bind=0.0.0.0:8000", "app:app"]