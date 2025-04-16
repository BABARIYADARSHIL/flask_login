import os
import cv2
import numpy as np
from face_auth.utils import get_device_mac, resize_image, upload_to_cloudinary, users_collection
from dotenv import load_dotenv
from deepface import DeepFace
from flask import request
from functools import wraps
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress TensorFlow warnings (handled in Dockerfile)
load_dotenv()
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "face_recognition")

# Rate limiting configuration
register_attempts = {}

def rate_limit(f):
    """
    Rate limit registration attempts (5 attempts per minute per IP).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        current_time = time.time()
        if client_ip in register_attempts:
            attempts, last_attempt = register_attempts[client_ip]
            if current_time - last_attempt < 60 and attempts >= 5:
                return {"error": "Too many registration attempts. Try again later.", "Status": "False"}, 429
            if current_time - last_attempt >= 60:
                register_attempts[client_ip] = [0, current_time]
        else:
            register_attempts[client_ip] = [0, current_time]
        register_attempts[client_ip][0] += 1
        return f(*args, **kwargs)
    return decorated_function

@rate_limit
def register_user(name, email, mobile, image_path=None):
    """
    Register a new user with facial recognition, using OpenCV backend for face detection.
    """
    temp_files = []
    try:
        # Sanitize inputs
        if not all([name, email, mobile]) or not all(isinstance(x, str) for x in [name, email, mobile]):
            logger.error("Invalid input: Name, email, and mobile must be non-empty strings")
            return {"error": "Name, email, and mobile are required and must be strings", "Status": "False"}
        if not image_path or not os.path.exists(image_path):
            logger.error(f"Invalid image path: {image_path}")
            return {"error": "Valid image path is required", "Status": "False"}

        # Check for existing user
        existing_user = users_collection.find_one({"email": email})
        if existing_user:
            logger.info(f"User with email {email} already registered")
            return {"error": "User with this email already registered", "Status": "False"}

        # Resize image
        resized_path = resize_image(image_path, width=128)
        if not resized_path or not os.path.exists(resized_path):
            logger.error(f"Failed to resize image: {image_path}")
            return {"error": "Invalid image file", "Status": "False"}
        temp_files.append(resized_path)

        # Detect face using OpenCV backend
        try:
            img = cv2.imread(resized_path)
            if img is None:
                logger.error(f"Failed to load image: {resized_path}")
                return {"error": "Invalid image file", "Status": "False"}
            detected_face = DeepFace.detectFace(
                img_path=img,
                detector_backend='opencv',  # Changed to avoid retinaface
                enforce_detection=True
            )
            if detected_face is None:
                logger.info(f"No face detected in image: {resized_path}")
                return {"error": "No face detected in the image", "Status": "False"}
        except Exception as e:
            logger.error(f"Face detection failed: {str(e)}")
            return {"error": f"No face detected in the image: {str(e)}", "Status": "False"}

        # Upload to Cloudinary
        cloudinary_url = upload_to_cloudinary(resized_path, folder=CLOUDINARY_FOLDER)
        if not cloudinary_url:
            logger.error("Failed to upload image to Cloudinary")
            return {"error": "Failed to upload image to Cloudinary", "Status": "False"}

        mac_address = get_device_mac()

        # Store user data
        user_data = {
            "name": name,
            "email": email,
            "mobile": mobile,
            "mac_address": mac_address,
            "image_url": cloudinary_url
        }
        users_collection.insert_one(user_data)
        logger.info(f"User registered successfully: {email}")

        return {
            "message": "User registered successfully",
            "Status": "True",
            "data": [
                {
                    "name": name,
                    "email": email,
                    "mobile": mobile,
                    "mac_address": mac_address,
                    "image_url": cloudinary_url
                }
            ]
        }

    except MemoryError:
        logger.error("Memory error during registration")
        return {"status": "error", "message": "Insufficient memory to process request", "code": 503}
    except Exception as e:
        error_msg = str(e)
        if "DeepFace" in error_msg:
            logger.error(f"DeepFace error: {error_msg}")
            return {"status": "error", "message": "Face detection failed", "code": 400}
        elif "Cloudinary" in error_msg:
            logger.error(f"Cloudinary error: {error_msg}")
            return {"status": "error", "message": "Cloudinary operation failed", "code": 503}
        elif "MongoDB" in error_msg or "pymongo" in error_msg:
            logger.error(f"Database error: {error_msg}")
            return {"status": "error", "message": "Database operation failed", "code": 503}
        else:
            logger.error(f"Unexpected error: {error_msg}")
            return {"status": "error", "message": "Application failed to respond", "code": 502}

    finally:
        # Clean up temporary files
        for path in temp_files:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info(f"Deleted temp image: {path}")
                except Exception as e:
                    logger.error(f"Failed to delete image {path}: {e}")
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                logger.info(f"Deleted temp image: {image_path}")
            except Exception as e:
                logger.error(f"Failed to delete image {image_path}: {e}")