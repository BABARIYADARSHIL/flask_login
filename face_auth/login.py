import cv2
import os
from face_auth.utils import get_device_mac, get_cloudinary_image, users_collection, upload_to_cloudinary, \
    delete_cloudinary_image, resize_image
from dotenv import load_dotenv
from deepface import DeepFace

load_dotenv()
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "face_recognition")

def login_user(email, image_path=None):
    try:
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

        # Fetch Cloudinary image as OpenCV image
        cloudinary_image = get_cloudinary_image(cloudinary_url)
        if cloudinary_image is None:
            return {"error": "Failed to fetch user image from Cloudinary", "Status": "False"}

        # Save Cloudinary image temporarily for DeepFace verification
        temp_cloudinary_path = "temp_cloudinary.jpg"
        cv2.imwrite(temp_cloudinary_path, cloudinary_image)

        resized_path = resize_image(image_path, width=256)
        if not resized_path or not os.path.exists(resized_path):
            return {"error": "Login image not found", "Status": "False"}

        # Use DeepFace to verify if faces match
        verification_result = DeepFace.verify(img1_path=resized_path, img2_path=temp_cloudinary_path, detector_backend='opencv',enforce_detection=True)

        # Clean up temp file
        if os.path.exists(temp_cloudinary_path):
            os.remove(temp_cloudinary_path)

        if verification_result["verified"]:
            # If verified, upload new login image and update DB as before
            if cloudinary_url:
                delete_success = delete_cloudinary_image(cloudinary_url)
                if not delete_success:
                    return {"error": "Failed to delete old image. Try again.", "Status": "False"}

            new_cloudinary_url = upload_to_cloudinary(resized_path, folder=CLOUDINARY_FOLDER)
            if not new_cloudinary_url:
                return {"error": "Failed to upload new login image.", "Status": "False"}

            users_collection.update_one(
                {"email": email},
                {"$set": {"image_url": new_cloudinary_url}}
            )

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
                        "isNewUser": user.get("isNewUser", ""),
                        "token": user.get("token", ""),
                        "dailyTotalWorkingHour": user.get("dailyTotalWorkingHour", ""),
                        "weeklyTotalWorkingHour": user.get("weeklyTotalWorkingHour", ""),
                        "requiresPasswordReset": user.get("requiresPasswordReset", ""),
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
        print(f"Unexpected error: {str(e)}")
        return {"status": "error", "message": "Application failed to respond", "code": 502}
    finally:
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                print(f"Deleted temp image: {image_path}")
            except Exception as e:
                print(f"Failed to delete image {image_path}: {e}")