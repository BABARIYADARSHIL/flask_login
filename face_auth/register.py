import os
from face_auth.utils import get_device_mac, resize_image, upload_to_cloudinary, users_collection
from dotenv import load_dotenv
from deepface import DeepFace

load_dotenv()
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "face_recognition")

def register_user(name, email, mobile, image_path=None):
    temp_image_path = None
    try:
        existing_user = users_collection.find_one({"$or": [{"email": email}]})
        if existing_user:
            if image_path and os.path.exists(image_path):
                os.remove(image_path)
            return {"error": "User with this email already registered"}

        resized_path = resize_image(image_path)
        if resized_path is None:
            return {"error": "Invalid image file"}

        # Use DeepFace to detect face by trying to analyze the image
        try:
            analysis = DeepFace.analyze(img_path=resized_path, actions=["age", "gender", "emotion", "race"])
            if isinstance(analysis, list):
                analysis = analysis[0]
            print("Face analysis result:", analysis)
        except Exception as e:
            print(f"Face detection failed: {e}")
            return {"error": "No face detected in the image"}

        # Upload to Cloudinary
        cloudinary_url = upload_to_cloudinary(resized_path, folder=CLOUDINARY_FOLDER)
        if not cloudinary_url:
            return {"error": "Failed to upload image to Cloudinary"}

        mac_address = get_device_mac()

        users_collection.insert_one({
            "name": name,
            "email": email,
            "mobile": mobile,
            "mac_address": mac_address,
            "image_url": cloudinary_url
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
                    "image_url": cloudinary_url
                }
            ]
        }

    except Exception as e:
        return {"error": str(e)}

    finally:
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                print(f"Deleted temp image: {image_path}")
            except Exception as e:
                print(f"Error deleting image: {e}")


