import os
import cv2
import numpy as np
from face_auth.utils import get_device_mac, resize_image, upload_to_cloudinary, users_collection
from dotenv import load_dotenv
from deepface import DeepFace
from flask import request
from functools import wraps
import time

load_dotenv()
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "face_recognition")

# Rate limiting configuration
register_attempts = {}

def rate_limit(f):
    """
    Rate limit registration attempts to prevent abuse (5 attempts per minute per IP).
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
    Register a new user with facial recognition and store their image in Cloudinary.
    Only registers if a face is detected in the image.
    """
    temp_files = []  # Track temporary files for cleanup
    try:
        # Sanitize inputs
        if not all([name, email, mobile]) or not all(isinstance(x, str) for x in [name, email, mobile]):
            return {"error": "Name, email, and mobile are required and must be strings", "Status": "False"}
        if image_path and not os.path.exists(image_path):
            return {"error": "Invalid image path", "Status": "False"}

        # Check for existing user
        existing_user = users_collection.find_one({"email": email})
        if existing_user:
            return {"error": "User with this email already registered", "Status": "False"}

        # Resize image
        resized_path = resize_image(image_path, width=128)  # Reduced to 128 for performance
        if not resized_path or not os.path.exists(resized_path):
            return {"error": "Invalid image file", "Status": "False"}
        temp_files.append(resized_path)

        # Use DeepFace to detect face (self-verification to ensure a face exists)
        try:
            img = cv2.imread(resized_path)
            verification_result = DeepFace.verify(
                img1_path=img,
                img2_path=img,  # Self-verification to check face presence
                detector_backend='ssd',
                model_name='Facenet512',  # Lighter model
                enforce_detection=True  # Strict face detection
            )
            if not verification_result["verified"]:
                return {"error": "No face detected in the image", "Status": "False"}
        except Exception as e:
            print(f"Face detection failed: {e}")
            return {"error": f"No face detected in the image: {str(e)}", "Status": "False"}

        # Upload to Cloudinary
        cloudinary_url = upload_to_cloudinary(resized_path, folder=CLOUDINARY_FOLDER)
        if not cloudinary_url:
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

    except Exception as e:
        error_msg = str(e)
        if "DeepFace" in error_msg:
            return {"status": "error", "message": "Face detection failed", "code": 400}
        elif "Cloudinary" in error_msg:
            return {"status": "error", "message": "Cloudinary operation failed", "code": 503}
        elif "MongoDB" in error_msg or "pymongo" in error_msg:
            return {"status": "error", "message": "Database operation failed", "code": 503}
        else:
            print(f"Unexpected error: {error_msg}")
            return {"status": "error", "message": "Application failed to respond", "code": 502}

    finally:
        # Clean up all temporary files
        for path in temp_files:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"Deleted temp image: {path}")
                except Exception as e:
                    print(f"Failed to delete image {path}: {e}")
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                print(f"Deleted temp image: {image_path}")
            except Exception as e:
                print(f"Failed to delete image {image_path}: {e}")