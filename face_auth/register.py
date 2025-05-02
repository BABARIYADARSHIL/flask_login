import cv2
import face_recognition
import os
from face_auth.utils import get_device_mac, resize_image, upload_to_cloudinary, users_collection
from dotenv import load_dotenv

load_dotenv()
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "face_recognition")

def register_user(name, email, mobile, image_path=None):
    temp_image_path = None  # track local file path for cleanup
    try:

        # **Check if user already exists**
        existing_user = users_collection.find_one({"$or": [{"email": email}]})
        if existing_user:
            # **Delete Uploaded Image if User Exists**
            if image_path and os.path.exists(image_path):   # Check if image_path is not None
                os.remove(image_path)

            return {"error": "User with this email already registered"}


        # **Resize Image Before Processing**
        resized_path = resize_image(image_path)
        if resized_path is None:
            return {"error": "Invalid image file"}

        # **Perform face detection on uploaded image**
        image = face_recognition.load_image_file(resized_path)
        face_locations = face_recognition.face_locations(image)

        if len(face_locations) == 0:
            return {"error": "In this image, no face is detected"}

        # **Upload to Cloudinary**
        cloudinary_url = upload_to_cloudinary(resized_path, folder=CLOUDINARY_FOLDER)
        if not cloudinary_url:
            return {"error": "Failed to upload image to Cloudinary"}

        # Get MAC address and IP address
        mac_address = get_device_mac()

        # **Store user data in MongoDB**
        users_collection.insert_one({
            "name": name,
            "email": email,
            "mobile": mobile,
            "mac_address": mac_address,
            "imageUrl": cloudinary_url  # Store Cloudinary image URL
        })

        return {
            "message": "User registered successfully",
            "Status": "True",
            "data": [
                {
                    "name": name,
                    "email": email,
                    "mobile": mobile,
                    "mac_address": mac_address,
                    "imageUrl": cloudinary_url
                }
            ]
        }

    except Exception as e:
        return {"error": str(e)}

    finally:
        # 🧹 Cleanup temp image file
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                print(f"Deleted temp image: {image_path}")
            except Exception as e:
                print(f"Error deleting image: {e}")

