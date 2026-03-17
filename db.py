"""
MongoDB connection module for Disaster Relief System.
Uses local MongoDB (localhost:27017) with database 'relief_system'.
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# MongoDB connection settings
MONGO_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "relief_system"

_client = None
_db = None


def get_db():
    """Get MongoDB database connection (singleton pattern)."""
    global _client, _db
    if _db is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Test connection
        try:
            _client.admin.command('ping')
        except ConnectionFailure:
            raise ConnectionError(
                "Could not connect to MongoDB. Make sure MongoDB is running on localhost:27017"
            )
        _db = _client[DATABASE_NAME]
    return _db


def get_collection(name: str):
    """Get a MongoDB collection by name."""
    return get_db()[name]


# Collection names
CAMPS_COLLECTION = "camps"
VICTIMS_COLLECTION = "victims"
RESPONDERS_COLLECTION = "responders"
SETTINGS_COLLECTION = "settings"
REQUESTS_COLLECTION = "requests"


def close_connection():
    """Close MongoDB connection."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
