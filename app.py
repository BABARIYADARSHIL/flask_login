from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from face_auth import register_user, login_user  # Import from the module
from face_auth.utils import upload_to_cloudinary,users_collection
from dotenv import load_dotenv

app = Flask(__name__)
CORS(app)
load_dotenv()

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "face_recognition")

@app.route('/register', methods=['POST'])
def register():
    try:
        name = request.form.get("name")
        email = request.form.get("email")
        mobile = request.form.get("mobile")
        image_file = request.files.get("image")

        if not name or not email or not mobile or not image_file:
            return jsonify({"error": "Name, Email, Mobile, and Image are required"}), 400

        # image_path = None  # Default value for webcam case
        # if image_file:
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], image_file.filename)
        image_file.save(image_path)

        # Pass image_path (even if None)
        response = register_user(name, email, mobile, image_path)

        return jsonify(response), 201 if "message" in response else 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        email = request.form.get("email")
        image_file = request.files.get("image")

        if not email or not image_file:
            return jsonify({"error": "Email and image are required"}), 400

        # Check for stored Cloudinary image URL
        user = users_collection.find_one({"email": email})
        if user is None:
            return jsonify({"error": "User not found"}), 404

        cloudinary_url = user.get("image_url")

        # **🚨 If image URL is missing, suggest capture/upload API**
        if not cloudinary_url:
            return jsonify({
                "error": "User image not found. Please capture or upload an image.",
                "capture_api": "/capture_upload_image"
            }), 400

        # If image file is uploaded, process it
        image_path = None
        if image_file:
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{email}_login.jpg")
            image_file.save(image_path)

        response = login_user(email, image_path)

        status_code = 200 if "message" in response else 401
        return jsonify(response), status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# # 🚀 New API: Handle webcam capture or manual upload
# @app.route('/capture_upload_image', methods=['POST'])
# def capture_upload_image():
#     try:
#         email = request.form.get("email")
#         print(email)
#         if not email:
#             return jsonify({"error": "Email is required"}), 400
#
#         # Check if user uploaded an image (for mobile users)
#         if "image" in request.files:
#             file = request.files["image"]
#             filename = os.path.join(app.config["UPLOAD_FOLDER"], f"{email}_upload.jpg")
#             file.save(filename)
#             cloudinary_url = upload_to_cloudinary(filename, folder=CLOUDINARY_FOLDER)
#             os.remove(filename)
#         else:
#             # **Webcam Capture Logic**
#             cap = cv2.VideoCapture(0)
#             if not cap.isOpened():
#                 return {"error": "Webcam not detected. Please upload an image manually."}
#             face_detected_time = None
#
#             while True:
#                 ret, frame = cap.read()
#                 if not ret:
#                     return {"error": "Failed to capture image"}
#
#                 # Convert frame to RGB
#                 rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#
#                 # Detect Face
#                 face_locations = face_recognition.face_locations(rgb_frame)
#
#                 if len(face_locations) == 0:
#                     face_detected_time = None  # Reset if face not found
#                     cv2.putText(frame, "No face detected!", (50, 50),
#                                 cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
#                 else:
#                     for (top, right, bottom, left) in face_locations:
#                         padding = 30
#                         cv2.rectangle(frame,
#                                       (left - padding, top - padding),
#                                       (right + padding, bottom + padding),
#                                       (0, 255, 0), 2)
#                     if face_detected_time is None:
#                         face_detected_time = time.time()
#
#                     # Calculate how long face has been detected
#                     elapsed = time.time() - face_detected_time
#                     remaining = 3 - int(elapsed)
#
#                     if elapsed >= 3:
#                         break  # Capture image
#
#                     # Show countdown on frame
#                     cv2.putText(frame, f"Hold still... {remaining}", (50, 450),
#                                 cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 0), 3)
#
#                 cv2.imshow("Face Capture - Hold still for 3 seconds", frame)
#                 if cv2.waitKey(1) & 0xFF == ord('q'):
#                     cap.release()
#                     cv2.destroyAllWindows()
#                     return {"error": "Face Capture cancelled by user"}
#
#             cap.release()
#             cv2.destroyAllWindows()
#
#             # Save & Upload Image to Cloudinary
#             filename = os.path.join(app.config["UPLOAD_FOLDER"], f"{email}_capture.jpg")
#             cv2.imwrite(filename, frame)
#             cloudinary_url = upload_to_cloudinary(filename, folder=CLOUDINARY_FOLDER)
#             os.remove(filename)
#
#         if not cloudinary_url:
#             return jsonify({"error": "Image upload failed"}), 500
#
#         # Update user profile with new image URL
#         users_collection.update_one({"email": email}, {"$set": {"image_url": cloudinary_url}})
#
#         return jsonify({ "success": True,"message": "Image captured & uploaded successfully", "image_url": cloudinary_url})
#
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Get PORT from environment
    app.run(host='0.0.0.0', port=port)
    # app.run(debug=True)
    # app.run(host='192.168.1.13', port=5000, debug=True)
