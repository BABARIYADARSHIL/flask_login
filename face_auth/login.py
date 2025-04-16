import cv2
import os
import numpy as np
from face_auth.utils import get_device_mac, get_cloudinary_image, users_collection, upload_to_cloudinary, \
    delete_cloudinary_image, resize_image
from dotenv import load_dotenv
from deepface import DeepFace
from flask import request
from functools import wraps
import time

load_dotenv()
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "face_recognition")

# Rate limiting configuration
login_attempts = {}

def rate_limit(f):
    """
    Rate limit login attempts to prevent abuse (5 attempts per minute per IP).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        current_time = time.time()
        if client_ip in login_attempts:
            attempts, last_attempt = login_attempts[client_ip]
            if current_time - last_attempt < 60 and attempts >= 5:
                return {"error": "Too many login attempts. Try again later.", "Status": "False"}, 429
            if current_time - last_attempt >= 60:
                login_attempts[client_ip] = [0, current_time]
        else:
            login_attempts[client_ip] = [0, current_time]
        login_attempts[client_ip][0] += 1
        return f(*args, **kwargs)
    return decorated_function

@rate_limit
def login_user(email, image_path=None):
    """
    Authenticate a user via facial recognition using DeepFace and update their image in Cloudinary.
    """
    temp_files = []  # Track temporary files for cleanup
    try:
        # Sanitize inputs
        if not email or not isinstance(email, str):
            return {"error": "Invalid email", "Status": "False"}
        if image_path and not os.path.exists(image_path):
            return {"error": "Invalid image path", "Status": "False"}

        mac_address = get_device_mac()
        user = users_collection.find_one({"email": email})

        if user is None:
            return {"error": "User not found", "Status": "False"}

        cloudinary_url = user.get("image_url")
        if not cloudinary_url:
            return {
                "error": "User image not found. Please capture/upload an image.",
                "capture_api": "/api/capture_upload_image",
                "Status": "False"
            }

        # Fetch Cloudinary image directly
        cloudinary_image = get_cloudinary_image(cloudinary_url)
        if cloudinary_image is None:
            return {"error": "Failed to fetch user image from Cloudinary", "Status": "False"}

        # Resize input image
        resized_path = resize_image(image_path, width=128)  # Reduced to 128 for performance
        if not resized_path or not os.path.exists(resized_path):
            return {"error": "Login image not found", "Status": "False"}
        temp_files.append(resized_path)

        # Use DeepFace to verify faces (pass cloudinary_image as NumPy array)
        verification_result = DeepFace.verify(
            img1_path=resized_path,
            img2_path=cloudinary_image,  # Direct NumPy array
            detector_backend='ssd',
            model_name='Facenet512',  # Lighter model
            enforce_detection=False  # Less strict for performance
        )

        if verification_result["verified"]:
            # Delete old Cloudinary image
            if cloudinary_url:
                delete_success = delete_cloudinary_image(cloudinary_url)
                if not delete_success:
                    return {"error": "Failed to delete old image. Try again.", "Status": "False"}

            # Upload new login image
            new_cloudinary_url = upload_to_cloudinary(resized_path, folder=CLOUDINARY_FOLDER)
            if not new_cloudinary_url:
                return {"error": "Failed to upload new login image.", "Status": "False"}

            # Update database
            users_collection.update_one(
                {"email": email},
                {"$set": {"image_url": new_cloudinary_url}}
            )

            # Prepare response
            return {
                "message": "Login successful",
                "Status": "True",
                "data": [
                    {
                        "_id": str(user.get("_id", "")),
                        "firstName": user.get("firstName", ""),
                        "lastName": user.get("lastName", ""),
                        "companyId": user.get("companyId", ""),
                        "companyName": user.get("companyName", ""),
                        "designation": user.get("designation", ""),
                        "email": email,
                        "phone": user.get("phone", ""),
                        "status": user.get("status", ""),
                        "role": user.get("role", ""),
                        "isNewUser": user.get("isNewUser", False),
                        "token": user.get("token", ""),  # Ensure token is secure
                        "dailyTotalWorkingHour": user.get("dailyTotalWorkingHour", ""),
                        "weeklyTotalWorkingHour": user.get("weeklyTotalWorkingHour", ""),
                        "requiresPasswordReset": user.get("requiresPasswordReset", False),
                        "empCode": user.get("empCode", ""),
                        "name": user.get("name", ""),
                        "mobile": user.get("mobile", ""),
                        "device_mac": mac_address,
                        "image_url": new_cloudinary_url,
                    }
                ]
            }
        else:
            return {"error": "Login failed. Face does not match.", "Status": "False"}

    except Exception as e:
        error_msg = str(e)
        if "DeepFace" in error_msg:
            return {"status": "error", "message": "Face verification failed", "code": 400}
        elif "Cloudinary" in error_msg:
            return {"status": "error", "message": "Cloudinary operation failed", "code": 503}
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