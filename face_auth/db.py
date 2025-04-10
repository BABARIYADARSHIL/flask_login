from pymongo import MongoClient
import os
from dotenv import load_dotenv  # Import load_dotenv from dotenv

# Load environment variables from .env file
load_dotenv()  # This will load the variables from .env into the environment

def db_connection(db_name=None):
    """Connect to MongoDB database."""
    # Fetch the MongoDB URI from environment variables or use a default
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")  # Default to local if not set
    db_name = db_name or os.getenv("MONGO_DB_NAME", "face_auth_data")  # Fetch from env or use default

    client = MongoClient(mongo_uri)

    # Print the MongoDB URI
    print(f"MONGO_URI: {mongo_uri}")
    print(db_name)
    # Use the provided db_name or default to 'face_auth_data'
    db = client[db_name]
    return db
