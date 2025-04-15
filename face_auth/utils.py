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

load_dotenv()
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "face_recognition")

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
def resize_image(image_path, width=500):
    image = cv2.imread(image_path)
    if image is None:
        return None  # Invalid image file

    height = int((image.shape[0] / image.shape[1]) * width)  # Maintain aspect ratio
    resized_image = cv2.resize(image, (width, height))  # Resize image

    cv2.imwrite(image_path, resized_image)  # Overwrite original image with resized image
    return image_path

# Function to upload image to Cloudinary
def upload_to_cloudinary(image_path, folder=CLOUDINARY_FOLDER):
    try:
        print(f"Uploading image: {image_path}")

        if not os.path.exists(image_path):
            print(f"Error: Image file {image_path} does not exist!")
            return None

        timestamp = int(time.time())  # Get the correct UNIX timestamp

        response = cloudinary.uploader.upload(
            image_path,
            folder=folder,
            timestamp=timestamp
        )

        # print("Cloudinary Response:", response)
        return response.get("secure_url")
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


# Function to get Cloudinary Image as OpenCV format

def get_cloudinary_image(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None
        # Convert to NumPy array and load into OpenCV
        img_array = np.frombuffer(response.content, np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return image if image is not None else None
    except requests.RequestException as e:
        print(f"Cloudinary image fetch error: {e}")
        return None

def upload_to_cloudinary_use_login(image, folder=CLOUDINARY_FOLDER):
    try:
        # If the image is a numpy array (e.g., from webcam), save it as a temporary file
        if isinstance(image, np.ndarray):  # Check if the input is a numpy array (image frame)
            # Create a temporary file to save the image (using time-based naming)
            timestamp = int(time.time())  # Generate a unique timestamp for file naming
            temp_file_path = f"temp_image_{timestamp}.jpg"
            cv2.imwrite(temp_file_path, image)  # Save the numpy array to a .jpg file
            image_path = temp_file_path  # Update image_path to point to the temporary file
        else:
            # If the image is already a file path (for mobile upload), use it directly
            image_path = image

        print(f"Uploading image: {image_path}")

        if not os.path.exists(image_path):
            print(f"Error: Image file {image_path} does not exist!")
            return None

        # Upload the image file to Cloudinary
        response = cloudinary.uploader.upload(
            image_path,
            folder=folder,
            timestamp=int(time.time())
        )

        # Clean up by removing the temporary image file if it was created
        if isinstance(image, np.ndarray):
            os.remove(image_path)

        return response.get("secure_url")
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None


def delete_cloudinary_image(image_url):
    try:
        # Extract public_id correctly (remove version and file extension)
        parts = image_url.split("/")
        public_id = "/".join(parts[-2:]).split(".")[0]  # Keep folder + filename

        print(f"Deleting Cloudinary Image: {public_id}")  # Debugging

        response = cloudinary.uploader.destroy(public_id)

        if response.get("result") == "ok":
            print("✅ Old image deleted successfully.")
            return True
        else:
            print("❌ Failed to delete old image. Response:", response)
            return False

    except Exception as e:
        print(f"❌ Error deleting image from Cloudinary: {e}")
        return False


# def show_countdown_with_face_detection(window_title="Hold still...", duration=3):
#     cap = cv2.VideoCapture(0)
#     if not cap.isOpened():
#         return None, "Webcam not detected"
#
#     face_detected_time = None
#     final_frame = None
#
#     while True:
#         ret, frame = cap.read()
#         if not ret:
#             cap.release()
#             return None, "Failed to capture image"
#
#         rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#         face_locations = face_recognition.face_locations(rgb_frame)
#
#         if len(face_locations) == 0:
#             face_detected_time = None
#             cv2.putText(frame, "No face detected!", (50, 50),
#                         cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
#         else:
#             for (top, right, bottom, left) in face_locations:
#                 padding = 30
#                 cv2.rectangle(frame,
#                               (left - padding, top - padding),
#                               (right + padding, bottom + padding),
#                               (0, 255, 0), 2)
#
#             if face_detected_time is None:
#                 face_detected_time = time.time()
#
#             elapsed = time.time() - face_detected_time
#             remaining = duration - int(elapsed)
#
#             if elapsed >= duration:
#                 final_frame = frame
#                 break
#
#             cv2.putText(frame, f"Hold still... {remaining}", (50, 450),
#                         cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 0), 3)
#
#         cv2.imshow(window_title, frame)
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             cap.release()
#             cv2.destroyAllWindows()
#             return None, "Operation cancelled by user"
#
#     cap.release()
#     cv2.destroyAllWindows()
#     return final_frame, None


def detect_face_encoding(image):
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    encodings = face_recognition.face_encodings(rgb_image)
    return encodings[0] if encodings else None