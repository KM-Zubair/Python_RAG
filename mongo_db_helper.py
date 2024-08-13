import os
import json
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import quote, urlparse
from cos import cos_client, COS_ENDPOINT, cos_bucket_name
from mdb import mdb_client
import streamlit as st

load_dotenv()

# Load environment variables
uri = os.getenv("MONGO_DB_URI")
if not uri:
    raise ValueError("MONGO_DB_URI is not set in the environment variables")

COS_ENDPOINT = os.getenv("COS_ENDPOINT")
if not COS_ENDPOINT:
    raise ValueError("COS_ENDPOINT is not set in the environment variables")

cos_bucket_name = os.getenv("COS_BUCKET_NAME")
if not cos_bucket_name:
    raise ValueError("COS_BUCKET_NAME is not set in the environment variables")

# Extract database name from URI
db_name = urlparse(uri).path.strip('/')
if not db_name:
    raise ValueError("Database name not found in MONGO_DB_URI")

db = mdb_client[db_name]
documents_collection = db["collection"]  # Using "collection" as in the first file

def upload_file_cos(file_path, file_name, file_id, file_size, chunk_ids):
    cos_client.upload_file(Filename=file_path, Bucket=cos_bucket_name, Key=file_name)
    
    file_meta_data = {
        "_id": file_id,
        "file_name": file_name,
        "file_url": f"{COS_ENDPOINT}/{cos_bucket_name}/{quote(file_name)}",
        "file_size": file_size,
        "chunk_ids": chunk_ids,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    documents_collection.insert_one(file_meta_data)

questions_collection = db["questions"] 

def insert_questions(bytes_data):
    json_string = bytes_data.decode('utf8')
    json_object = json.loads(json_string)
    questions_collection.insert_many(json_object)

def get_questions():
    return list(questions_collection.find({}))
