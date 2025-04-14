import cv2
import os
import face_recognition
from face_auth.utils import get_device_mac, get_cloudinary_image, users_collection,upload_to_cloudinary, delete_cloudinary_image, show_countdown_with_face_detection
from dotenv import load_dotenv

load_dotenv()
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "face_recognition")

def login_user(email, image_path=None):
    try:
        # Get Device MAC and IP Address
        mac_address = get_device_mac()

        # **Fetch stored user details from MongoDB**
        user = users_collection.find_one({"email": email})

        if user is None:
            return {"error": "User not found", "Status": "False"}


        # _id = str(user.get("_id", ""))
        # firstName = user.get("firstName", "")
        # lastName = user.get("lastName", "")
        # companyId = user.get("companyId", "")
        # companyName = user.get("companyName", "")
        # designation = user.get("designation", "")
        # phone = user.get("phone", "")
        # status = user.get("status", "")
        # role = user.get("role", "")
        # isNewUser = user.get("isNewUser", "")
        # token = user.get("token", "")
        # dailyTotalWorkingHour = user.get("dailyTotalWorkingHour", "")
        # weeklyTotalWorkingHour = user.get("weeklyTotalWorkingHour", "")
        # requiresPasswordReset = user.get("requiresPasswordReset", "")
        # empCode = user.get("empCode", "")
        # name = user.get("name", "")
        # mobile = user.get("mobile", "")

        stored_mac = user["mac_address"]
        cloudinary_url = user.get("image_url")  # Get image URL from Cloudinary

        # **Fetch the Cloudinary image**
        cloudinary_image = get_cloudinary_image(cloudinary_url) if cloudinary_url else None

        # **Check if User Has an Image in Database**

        if not cloudinary_url or cloudinary_image is None:
            return {
                "error": "User image not found. Please capture/upload an image.",
                "capture_api": "/api/capture_upload_image",  # API for capturing & uploading
                "Status": "False"
            }
        # Convert Cloudinary image to face encoding

        cloudinary_rgb = cv2.cvtColor(cloudinary_image, cv2.COLOR_BGR2RGB)
        cloudinary_encoding = face_recognition.face_encodings(cloudinary_rgb)

        if len(cloudinary_encoding) == 0:
            return {"error": "No face detected in Cloudinary image","Status": "False"}

        cloudinary_encoding = cloudinary_encoding[0]  # Get first face encoding

        # Set default image path for local storage
        # temp_image_path = f"uploads/{email}_login.jpg"

        # **Check if login is from Mobile or PC**
        # if image_path:  # Mobile Login (file upload)
        image = face_recognition.load_image_file(image_path)
        encoding = face_recognition.face_encodings(image)

        # else:  # PC Login (Webcam)
        #     frame, error = show_countdown_with_face_detection(window_title="Face Login")
        #     if error:
        #         return {"error": error, "Status": "False"}
        #
        #     # # Resize Webcam Image
        #     frame_resized  = cv2.resize(frame, (500, int((frame.shape[0] / frame.shape[1]) * 500)))  # Maintain aspect ratio
        #
        #     # Convert frame to encoding
        #     rgb_frame = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
        #     encoding = face_recognition.face_encodings(rgb_frame)
        #
        #     # Save captured image
        #     # image_path = f"uploads/{email}_login.jpg"
        #     # cv2.imwrite(image_path, frame_resized)
        #     cv2.imwrite(temp_image_path, frame_resized)
        #     image_path = temp_image_path
        #
        #     # **MAC and IP check only for PC login**
        #     if mac_address != stored_mac:
        #         return {"error": "Unauthorized device! MAC/IP mismatch. Request admin verification.","Status": "False"}
        if not encoding:
            return {"error": "No face detected for login","Status": "False"}

        # **Compare the face encoding with Cloudinary image using distance**
        distance = face_recognition.face_distance([cloudinary_encoding], encoding[0])[0]  # Get similarity score
        print(distance)
        threshold = 0.4  # Stricter threshold for better accuracy

        if distance < threshold:
            # Delete old Cloudinary image if exists
            if cloudinary_url:
                delete_success = delete_cloudinary_image(cloudinary_url)
                if not delete_success:
                    return {"error": "Failed to delete old image. Try again.","Status": "False"}
            print(f"Uploading new image: {image_path}")  # Debugging
            new_cloudinary_url = upload_to_cloudinary(image_path, folder=CLOUDINARY_FOLDER)

            if not new_cloudinary_url:
                return {"error": "Failed to upload new login image.","Status": "False"}

            # Update MongoDB with new image URL
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

        return {"error": "Login failed. Face does not match.", "Status": "False"}

    except Exception as e:
        return {"error": str(e)}
    finally:
        # 🧹 Cleanup: Delete the local image after processing (success or fail)
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                print(f"Deleted temp image: {image_path}")
            except Exception as e:
                print(f"Failed to delete image {image_path}: {e}")
