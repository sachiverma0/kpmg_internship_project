
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
from azure.cosmos import CosmosClient

# Load environment variables
load_dotenv()

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DB_NAME = os.getenv("COSMOS_DB_NAME")
COSMOS_CONTAINER_NAME = os.getenv("COSMOS_CONTAINER_NAME")

# Initialize Cosmos client
client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
database = client.get_database_client(COSMOS_DB_NAME)
container = database.get_container_client(COSMOS_CONTAINER_NAME)

app = Flask(__name__)

@app.route("/add", methods=["POST"])
def add_message():
    data = request.json
    item = {
        "id": data["id"],  # must match partition key
        "text": data["text"]
    }
    container.create_item(item)
    return jsonify({"status": "success", "item": item})

@app.route("/messages", methods=["GET"])
def list_messages():
    query = "SELECT * FROM c"
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    return jsonify(items)

if __name__ == "__main__":
    app.run(debug=True)
