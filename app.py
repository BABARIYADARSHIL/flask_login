from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from face_auth import register_user, login_user , request_face_verification, reset_face_data, log_memory_usage
from dotenv import load_dotenv
import base64
import uuid
import logging

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
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], image_file.filename)
        image_file.save(image_path)

        # Pass image_path (even if None)
        response = register_user(name, email, mobile, image_path)

        # return jsonify(response), 201 if "message" in response else 400
        return jsonify(response), 201 if response.get("status") == "success" else 400

    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "code": 500}), 500

@app.route('/login', methods=['POST'])
def login():
    print("start")
    log_memory_usage()
    try:
        data = request.get_json()
        if not data or 'username' not in data or 'image' not in data:
            return jsonify({"status": False, "message": "username and image are required", "code": 400}), 400
        email = data['username']
        base64_image = data['image']

        # Decode base64 image
        try:
            if ';base64,' in base64_image:
                base64_string = base64_image.split(';base64,')[1]
            else:
                base64_string = base64_image
            image_data = base64.b64decode(base64_string)
        except Exception as e:
            return jsonify({"status": False, "message": "Invalid base64 image", "code": 400}), 400

        image_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{email}_{uuid.uuid4()}.jpg")
        with open(image_path, 'wb') as f:
            f.write(image_data)

        response = login_user(email, image_path)
        log_memory_usage()
        print("Endaa")
 
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                logging.error(f"Failed to delete image {image_path}: {e}")

        status_code = 200
        if response.get("status") == "success":
            status_code = 200
        elif response.get("status") == "pending":
            status_code = 202  # Accepted, pending approval
        elif response.get("status") == "error":
            status_code = response.get("code", 200)
        return jsonify(response), status_code
   


    except Exception as e:
        print("Exception in login route:", str(e))
        log_memory_usage()
        print("End")

        return jsonify({"status": False, "message": str(e), "code": 500}), 500

@app.route('/request-face-verification', methods=['POST'])
def request_face_verification_endpoint():
    try:
        data = request.get_json()
        if not data or 'username' not in data or 'image' not in data:
            return jsonify({"status": False, "message": "username and image are required", "code": 400}), 400

        email = data['username']
        base64_image = data['image']

        try:
            if ';base64,' in base64_image:
                base64_string = base64_image.split(';base64,')[1]
            else:
                base64_string = base64_image
            image_data = base64.b64decode(base64_string)
        except Exception as e:
            return jsonify({"status": False, "message": "Invalid base64 image", "code": 400}), 400

        image_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{email}_{uuid.uuid4()}.jpg")
        with open(image_path, 'wb') as f:
            f.write(image_data)

        response = request_face_verification(email, image_path)

        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                logging.error(f"Failed to delete image {image_path}: {e}")

        status_code = 200 if response.get("status") is True else response.get("code", 400)
        return jsonify(response), status_code

    except Exception as e:
        return jsonify({"status": False, "message": str(e), "code": 500}), 500


@app.route('/forgot-face-login', methods=['POST'])
def forgot_face_login():
    try:
        data = request.get_json()
        if not data or 'username' not in data or 'image' not in data:
            return jsonify({"status": False, "message": "username and image are required", "code": 400}), 400

        email = data['username']
        base64_image = data['image']

        try:
            if ';base64,' in base64_image:
                base64_string = base64_image.split(';base64,')[1]
            else:
                base64_string = base64_image
            image_data = base64.b64decode(base64_string)
        except Exception as e:
            logging.error(f"Invalid base64 image: {e}")
            return jsonify({"status": False, "message": "Invalid base64 image", "code": 400}), 400

        image_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{email}_{uuid.uuid4()}.jpg")
        with open(image_path, 'wb') as f:
            f.write(image_data)
        response = reset_face_data(email, image_path)

        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                logging.error(f"Failed to delete image {image_path}: {e}")

        status_code = 200 if response.get("status") is True else response.get("code", 400)
        return jsonify(response), status_code

    except Exception as e:
        logging.error(f"Error in forgot_face_login: {e}")
        return jsonify({"status": False, "message": str(e), "code": 500}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port, debug=True)

