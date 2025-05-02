import cv2
import os
import face_recognition
from face_auth.utils import get_cloudinary_image, users_collection, upload_to_cloudinary, \
    delete_cloudinary_image, generate_token, resize_image
from dotenv import load_dotenv
from bson import ObjectId
from datetime import datetime
import time
import logging
from pymongo import MongoClient

load_dotenv()
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "face_recognition")

logging.basicConfig(filename="face_auth.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB_NAME")]
faceverification_collection = db["faceverifications"]

def convert_to_serializable(data):
    """Convert ObjectId and datetime to JSON-serializable formats."""
    if isinstance(data, ObjectId):
        return str(data)
    if isinstance(data, datetime):
        return data.isoformat()  # Convert datetime to ISO string
    if isinstance(data, dict):
        return {k: convert_to_serializable(v) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_to_serializable(item) for item in data]
    return data

def request_face_verification(email, image_path):
    start_time = time.time()
    try:
        # Fetch user details
        user = users_collection.find_one({"email": email})
        if user is None:
            return {"status": False, "message": "User not found", "code": 400}

        # Resize and validate image
        image_path = resize_image(image_path)
        if not image_path or not os.path.exists(image_path):
            return {"status": False, "message": "Image processing failed", "code": 400}

        try:
            image = face_recognition.load_image_file(image_path)
        except Exception as e:
            logging.error(f"Failed to load image file: {e}")
            return {"status": False, "message": "Invalid image file", "code": 400}

        try:
            face_encodings = face_recognition.face_encodings(image, model="hog")
        except Exception as e:
            logging.error(f"Failed to get face encodings: {e}")
            return {"status": False, "message": "Face encoding failed", "code": 400}

        if not face_encodings:
            return {"status": False, "message": "No face detected in the login image", "code": 400}

        # Upload image to Cloudinary
        upload_start = time.time()
        new_cloudinary_url = upload_to_cloudinary(image_path, folder=CLOUDINARY_FOLDER)
        logging.info(f"Cloudinary upload took {time.time() - upload_start:.3f} seconds")
        if not new_cloudinary_url:
            return {"status": False, "message": "Failed to upload login image to Cloudinary", "code": 400}

        # Check for existing pending request
        existing_request = faceverification_collection.find_one({
            "userId": user.get("_id", ""),
            "status": "pending"
        })

        if existing_request:
            logging.info(f"Pending face verification request already exists for {email}")
            return {
                "status": False,
                "message": "A pending face verification request already exists for this user.",
                "data": convert_to_serializable(existing_request),
                "code": 400
            }

        # Store data in faceverificationrequests collection
        login_request_data = {
            "companyId": user.get("companyId", ""),
            "imageUrl": new_cloudinary_url,
            "createdAt": datetime.utcnow(),
            "status": "pending",
            "userId": user.get("_id", ""),
            "updatedAt": datetime.utcnow()
        }
        faceverification_collection.insert_one(login_request_data)
        logging.info(f"Stored login attempt in faceverificationrequests for {email}")

        return {
            "status": True,
            "message": "Your face verification request has been sent successfully.",
            "data": convert_to_serializable(login_request_data),
            "code": 200
        }

    except Exception as e:
        logging.error(f"Unexpected error in request_face_verification: {e}")
        return {"status": False, "message": "Application failed to respond", "code": 500}
    finally:
        # Cleanup local image
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                logging.info(f"Deleted temp image: {image_path}")
            except Exception as e:
                logging.error(f"Failed to delete image {image_path}: {e}")


def login_user(email, image_path=None):
    start_time = time.time()
    try:
        query_start = time.time()
        # Fetch stored user details from MongoDB
        user = users_collection.find_one({"email": email})
        logging.info(f"MongoDB query took {time.time() - query_start:.3f} seconds")
        if user is None:
            return {"status": False, "message": "User not found", "code": 400}

        approved_request = faceverification_collection.find_one({
            "userId": user.get("_id", ""),
            "status": "approved"
        })

        # If no approved face verification exists, prompt for verification request
        if not approved_request:
            existing_request = faceverification_collection.find_one({
                "userId": user.get("_id", ""),
                "status": "pending"
            })
            if existing_request:
                logging.info(f"Pending face verification request already exists for {email}")
                return {
                    "status": False,
                    "message": "A pending face verification request already exists for this user.",
                    "data": convert_to_serializable(existing_request),
                    "isPopupOpen": False,
                    "code": 400
                }
            # No approved or pending request, prompt frontend to submit a verification request
            return {
                "status": False,
                "message": "No approved face verification found. Please submit a verification request.",
                "isPopupOpen": True,
                "code": 400
            }

        # Fetch Cloudinary image
        cloudinary_fetch_start = time.time()
        cloudinary_url = approved_request.get("imageUrl")
        cloudinary_image = get_cloudinary_image(cloudinary_url)
        logging.info(f"Cloudinary fetch took {time.time() - cloudinary_fetch_start:.3f} seconds")
        if cloudinary_image is None:
            return {"status": False, "message": "Failed to fetch Cloudinary image", "code": 400}


        face_encoding_start = time.time()
        # Convert Cloudinary image to face encoding
        try:
            cloudinary_rgb = cv2.cvtColor(cloudinary_image, cv2.COLOR_BGR2RGB)
            cloudinary_encodings = face_recognition.face_encodings(cloudinary_rgb, model="hog")
        except Exception as e:
            logging.error(f"Failed to process Cloudinary image: {e}")
            return {"status": False, "message": "Cloudinary image processing failed", "code": 400}

        if not cloudinary_encodings:
            return {"status": False, "message": "No face detected in Cloudinary image", "code": 400}
        logging.info(f"Cloudinary face encoding took {time.time() - face_encoding_start:.3f} seconds")
        cloudinary_encoding = cloudinary_encodings[0]

        # Load and encode the input image
        input_encoding_start = time.time()
        image_path = resize_image(image_path)
        if not image_path or not os.path.exists(image_path):
            return {"status": False, "message": "Image processing failed", "code": 400}

        try:
            image = face_recognition.load_image_file(image_path)
        except Exception as e:
            logging.error(f"Failed to load input image: {e}")
            return {"status": False, "message": "Invalid input image file", "code": 400}

        try:
            input_encodings = face_recognition.face_encodings(image, model="hog")
        except Exception as e:
            logging.error(f"Failed to get face encodings from input: {e}")
            return {"status": False, "message": "Face encoding failed for input", "code": 400}

        if not input_encodings:
            return {"status": False, "message": "No face detected for login", "code": 400}
        logging.info(f"Input image face encoding took {time.time() - input_encoding_start:.3f} seconds")

        encoding = input_encodings[0]

        # Compare faces
        compare_start = time.time()
        distance = face_recognition.face_distance([cloudinary_encoding], encoding)[0]
        logging.info(f"Face comparison took {time.time() - compare_start:.3f} seconds")
        logging.info(f"Face distance: {distance}")
        threshold = 0.4

        if distance < threshold:
            # Delete old Cloudinary image if exists
            if cloudinary_url:
                delete_success = delete_cloudinary_image(cloudinary_url)
                if not delete_success:
                    return {"status": False, "message": "Failed to delete old image. Try again.", "code": 400}

            # Upload new image
            upload_start = time.time()
            new_cloudinary_url = upload_to_cloudinary(image_path, folder=CLOUDINARY_FOLDER)
            logging.info(f"Cloudinary upload took {time.time() - upload_start:.3f} seconds")
            if not new_cloudinary_url:
                return {"status": False, "message": "Failed to upload new login image.", "code": 400}

            # Update MongoDB with new image URL
            update_start = time.time()
            faceverification_collection.update_one(
                {"_id": approved_request["_id"]},
                {"$set": {
                    "imageUrl": new_cloudinary_url,
                    "updatedAt": datetime.utcnow()
                }}
            )
            logging.info(f"MongoDB update took {time.time() - update_start:.3f} seconds")

            token_start = time.time()
            token = generate_token(user)
            logging.info(f"Token generation took {time.time() - token_start:.3f} seconds")
            if not token:
                return {"status": False, "message": "Failed to generate authentication token", "code": 400}

            data = {
                "_id": str(user.get("_id", "")),
                "firstName": user.get("firstName", ""),
                "lastName": user.get("lastName", ""),
                "companyId": str(user.get("companyId", "")),  # Convert ObjectId to string
                "companyName": user.get("companyName", ""),
                "designation": user.get("designation", ""),
                "email": email,
                "phone": user.get("phone", ""),
                "status": user.get("status", ""),
                "role": user.get("role", ""),
                "isNewUser": user.get("isNewUser", False),
                "token": token,
                "dailyTotalWorkingHour": user.get("dailyTotalWorkingHour", ""),
                "weeklyTotalWorkingHour": user.get("weeklyTotalWorkingHour", ""),
                "requiresPasswordReset": user.get("requiresPasswordReset", False),
                "empCode": user.get("empCode", ""),
                "imageUrl": new_cloudinary_url,
            }
            logging.info(f"Response data: {convert_to_serializable(data)}")
            logging.info(f"Total login time: {time.time() - start_time:.3f} seconds")

            return {
                "status": True,
                "message": "Login successful",
                "data": data
            }
        else:
            return {"status": False, "message": "Login failed. Face does not match.", "code": 400}

    except Exception as e:
        return {"status": False, "message": "Application failed to respond", "code": 500}
    finally:
        # Cleanup: Delete the local image
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                logging.info(f"Deleted temp image: {image_path}")
            except Exception as e:
                logging.error(f"Failed to delete image {image_path}: {e}")


def reset_face_data(email, image_path):
    start_time = time.time()
    try:
        # Fetch user details
        user = users_collection.find_one({"email": email})
        if user is None:
            return {"status": False, "message": "User not found", "code": 400}

        # Check faceverification_collection for existing requests
        user_id = user.get("_id")
        existing_request = faceverification_collection.find_one({"userId": user_id})

        # Check if there is a pending request
        if existing_request and existing_request.get("status") == "pending":
            return {
                "status": False,
                "message": "A pending face verification request already exists. Please wait for approval.",
                "data": convert_to_serializable({
                    "_id": str(existing_request["_id"]),
                    "imageUrl": existing_request.get("imageUrl"),
                    "status": "pending",
                    "userId": str(user_id)
                }),
                "code": 400
            }

        # Check if no request exists
        if not existing_request:
            return {
                "status": False,
                "message": "This user does not have a face verification record. Please submit a new request.",
                "code": 400
            }

        # Check if the existing request is not approved
        if existing_request.get("status") != "approved":
            return {
                "status": False,
                "message": "Only approved face verifications are eligible for changes.",
                "code": 400
            }


        # Resize and validate image
        image_path = resize_image(image_path)
        if not image_path or not os.path.exists(image_path):
            return {"status": False, "message": "Image processing failed", "code": 400}

        try:
            image = face_recognition.load_image_file(image_path)
        except Exception as e:
            logging.error(f"Failed to load image file: {e}")
            return {"status": False, "message": "Invalid image file", "code": 400}

        try:
            face_encodings = face_recognition.face_encodings(image, model="hog")
        except Exception as e:
            logging.error(f"Failed to get face encodings: {e}")
            return {"status": False, "message": "Face encoding failed", "code": 400}

        if not face_encodings:
            return {"status": False, "message": "No face detected in the provided image", "code": 400}

        # Upload new image to Cloudinary
        upload_start = time.time()
        new_cloudinary_url = upload_to_cloudinary(image_path, folder=CLOUDINARY_FOLDER)
        logging.info(f"Cloudinary upload took {time.time() - upload_start:.3f} seconds")
        if not new_cloudinary_url:
            return {"status": False, "message": "Failed to upload new image to Cloudinary", "code": 400}

        # Update the approved request to pending with the new image
        old_cloudinary_url = existing_request.get("imageUrl")
        update_start = time.time()
        faceverification_collection.update_one(
            {"_id": existing_request["_id"]},
            {"$set": {
                "imageUrl": new_cloudinary_url,
                "status": "pending",
                "updatedAt": datetime.utcnow()
            }}
        )
        logging.info(f"MongoDB update (approved to pending) took {time.time() - update_start:.3f} seconds")

        # Delete old Cloudinary image if it exists
        if old_cloudinary_url:
            delete_success = delete_cloudinary_image(old_cloudinary_url)
            if not delete_success:
                logging.warning(f"Failed to delete old Cloudinary image for {email}")

        return {
            "status": True,
            "message": "Face verification request updated to pending. Await approval.",
            "data": convert_to_serializable({
                "_id": str(existing_request["_id"]),
                "imageUrl": new_cloudinary_url,
                "status": "pending",
                "userId": str(user_id)
            }),
            "code": 200
        }

    except Exception as e:
        logging.error(f"Unexpected error in reset_face_data: {e}")
        return {"status": False, "message": "Application failed to respond", "code": 500}
    finally:
        # Cleanup local image
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                logging.info(f"Deleted temp image: {image_path}")
            except Exception as e:
                logging.error(f"Failed to delete image {image_path}: {e}")


import psutil
import os
def log_memory_usage():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    logging.info(f"Memory Usage: RSS={mem_info.rss / 1024 / 1024:.2f} MB, VMS={mem_info.vms / 1024 / 1024:.2f} MB")
    print(f"Memory Usage: RSS={mem_info.rss / 1024 / 1024:.2f} MB, VMS={mem_info.vms / 1024 / 1024:.2f} MB")