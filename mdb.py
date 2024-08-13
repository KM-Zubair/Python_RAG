import os
import certifi
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

uri = os.getenv("MONGO_DB_URI")
if not uri:
    raise ValueError("MONGO_DB_URI is not set in the environment variables")

mdb_client = MongoClient(uri, server_api=ServerApi('1'), tlsCAFile=certifi.where())

# Extract database name from URI
db_name = urlparse(uri).path.strip('/')
if not db_name:
    raise ValueError("Database name not found in MONGO_DB_URI")

db = mdb_client[db_name]
document_collection = db["collection"]  

def get_next_serial_number(collection):
    max_serial_number = collection.find_one({}, sort=[("_id", -1)])
    if max_serial_number is None:
        return 1  
    else:
        return max_serial_number["_id"] + 1
 
def is_document_exist(file_id):
    document = document_collection.find_one({'_id': file_id})
    return not not document

def get_many_documents():
    documents = document_collection.find({})
    return documents

def delete_many_documents(ids_to_delete):
    document_collection.delete_many({"_id": {"$in": ids_to_delete}})

# def test_connection():
#     try:
#         mdb_client.admin.command('ping')
#         print("Successfully connected to MongoDB!")
#     except Exception as e:
#         print(f"Failed to connect to MongoDB. Error: {e}")

# if __name__ == "__main__":
#     test_connection()