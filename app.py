from flask import Flask, request, jsonify
from pymongo import MongoClient
import bcrypt
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client['login_app']
users_collection = db['users']

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'status': 'error', 'message': 'Email and password required'}), 400

    user = users_collection.find_one({'email': email})
    if not user:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404

    if bcrypt.checkpw(password.encode('utf-8'), user['password']):
        return jsonify({'status': 'success', 'message': 'Login successful'}), 200
    else:
        return jsonify({'status': 'error', 'message': 'Invalid password'}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if users_collection.find_one({'email': email}):
        return jsonify({'status': 'error', 'message': 'Email already exists'}), 409

    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    users_collection.insert_one({'email': email, 'password': hashed_pw})

    return jsonify({'status': 'success', 'message': 'User registered'}), 201

if __name__ == '__main__':
    app.run(debug=True)
