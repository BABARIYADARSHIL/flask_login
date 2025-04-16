from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from face_auth.register import register_user  # Import from the module
from face_auth.login import  login_user  # Import from the module
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Get PORT from environment
    app.run(host='0.0.0.0', port=port)
    # app.run(debug=True)
    # app.run(host='192.168.1.13', port=5000, debug=True)
