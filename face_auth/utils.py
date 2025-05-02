import time
import cv2
import os
import face_recognition
import numpy as np
import requests
from getmac import get_mac_address
import cloudinary.uploader
from face_auth.cloudinary_config import cloudinary  # Import Cloudinary configuration
from face_auth.db import db_connection
from dotenv import load_dotenv
from cloudinary.uploader import destroy
import jwt
from datetime import datetime, timedelta
import threading
import logging

load_dotenv()
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "face_recognition")

# Configure logging
logging.basicConfig(filename="face_auth.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Fetch DB name from environment variable
db_name = os.getenv("MONGO_DB_NAME", "face_auth_db")  # Default to 'face_auth_db' if not set
collection_name = os.getenv("MONGO_COLLECTION_NAME", "users")  # Default 'users'

# Create Database Connection
db = db_connection(db_name)

# Fetch Collection Name from .env
users_collection = db[collection_name]  # ✅ Now using the collection name from .env

# Function to get MAC Address
def get_device_mac():
    mac = get_mac_address()
    return mac if mac else "Unknown"

# Function to Resize Image (Maintaining Aspect Ratio)
def resize_image(image_path, max_width=500):
    try:
        image = cv2.imread(image_path)
        if image is None:
            logging.error(f"Failed to read image: {image_path}")
            return None

        height, width = image.shape[:2]
        if width > max_width:
            ratio = max_width / width
            new_height = int(height * ratio)
            image = cv2.resize(image, (max_width, new_height), interpolation=cv2.INTER_AREA)
            cv2.imwrite(image_path, image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])  # Compress with 85% quality
        return image_path
    except Exception as e:
        logging.error(f"Error resizing image {image_path}: {e}")
        return None

# Function to upload image to Cloudinary
def upload_to_cloudinary(image_path, folder=CLOUDINARY_FOLDER):
    try:
        logging.info(f"Uploading image: {image_path}")
        if not os.path.exists(image_path):
            logging.error(f"Image file {image_path} does not exist")
            return None

        # Resize image before upload
        resized_path = resize_image(image_path)
        if not resized_path:
            return None

        response = cloudinary.uploader.upload(
            resized_path,
            folder=folder,
            timestamp=int(time.time()),
            quality="auto:low"  # Optimize upload size
        )
        return response.get("secure_url")
    except Exception as e:
        logging.error(f"Cloudinary upload error: {e}")
        return None

def get_cloudinary_image(url):
    try:
        response = requests.get(url, timeout=5)  # Reduced timeout
        if response.status_code != 200:
            logging.error(f"Failed to fetch Cloudinary image: {url}, status: {response.status_code}")
            return None
        img_array = np.frombuffer(response.content, np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if image is None:
            logging.error(f"Failed to decode Cloudinary image: {url}")
        return image
    except requests.RequestException as e:
        logging.error(f"Cloudinary image fetch error: {e}")
        return None

def upload_to_cloudinary_use_login(image, folder=CLOUDINARY_FOLDER):
    try:
        if isinstance(image, np.ndarray):
            timestamp = int(time.time())
            temp_file_path = f"temp_image_{timestamp}.jpg"
            cv2.imwrite(temp_file_path, image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            image_path = temp_file_path
        else:
            image_path = image

        logging.info(f"Uploading image: {image_path}")
        if not os.path.exists(image_path):
            logging.error(f"Image file {image_path} does not exist")
            return None

        response = cloudinary.uploader.upload(
            image_path,
            folder=folder,
            timestamp=int(time.time()),
            quality="auto:low"
        )

        if isinstance(image, np.ndarray):
            os.remove(image_path)
        return response.get("secure_url")
    except Exception as e:
        logging.error(f"Cloudinary upload error: {e}")
        return None

def delete_cloudinary_image(imageUrl, retries=2, delay=1):
    def async_delete(public_id):
        try:
            response = destroy(public_id)
            if response.get("result") in ["ok", "not found"]:
                logging.info(f"Image deleted or not found: {public_id}")
            else:
                logging.error(f"Failed to delete image: {public_id}, Response: {response}")
        except Exception as e:
            logging.error(f"Error deleting image {public_id}: {e}")

    try:
        parts = imageUrl.split("/")
        upload_index = parts.index("upload") + 1
        if parts[upload_index].startswith("v"):
            upload_index += 1
        public_id = "/".join(parts[upload_index:]).split(".")[0]
        logging.info(f"Queueing deletion of Cloudinary image: {public_id}")

        # Run deletion in a background thread
        threading.Thread(target=async_delete, args=(public_id,), daemon=True).start()
        return True
    except Exception as e:
        logging.error(f"Error queueing deletion: {e}")
        return False

def detect_face_encoding(image):
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    # Use HOG model for faster face detection
    encodings = face_recognition.face_encodings(rgb_image, model="hog")
    return encodings[0] if encodings else None


def generate_token(user):
    """
    Generate a JWT token for the user.

    Args:
        user (dict): User data to include in the token payload.

    Returns:
        str: JWT token.
    """
    try:
        # Prepare the payload (similar to user.toJSON())
        payload = {
            "_id": str(user.get("_id", "")),
            "firstName": user.get("firstName", ""),
            "lastName": user.get("lastName", ""),
            "companyId": str(user.get("companyId", "")),
            "designation": user.get("designation", ""),
            "email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "status": user.get("status", ""),
            "role": user.get("role", ""),
            "isNewUser": user.get("isNewUser", False),
            "empCode": user.get("empCode", ""),
            "password": user.get("password", ""),
            "createdAt": user.get("createdAt", datetime.utcnow()).isoformat() if user.get("createdAt") else "",
            "updatedAt": user.get("updatedAt", datetime.utcnow()).isoformat() if user.get("updatedAt") else "",
            "__v": user.get("__v", 0),
            # Add expiration (e.g., 1 hour from now)
            "iat": int(datetime.utcnow().timestamp())
        }

        # Get the JWT secret from environment
        secret = os.getenv("JWT_SECRET")
        if not secret:
            raise ValueError("JWT_SECRET not found in environment variables")

        # Generate the token with HS256
        token = jwt.encode(payload, secret, algorithm="HS256")
        return token

    except Exception as e:
        print(f"Error generating JWT token: {str(e)}")
        return None