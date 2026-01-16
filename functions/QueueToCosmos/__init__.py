

import json
import logging
import os
import azure.functions as func
from azure.cosmos import CosmosClient

from openai import AzureOpenAI

openai_client = AzureOpenAI(
    api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
)

COSMOS_ENDPOINT = os.environ["COSMOS_ENDPOINT"]
COSMOS_KEY = os.environ["COSMOS_KEY"]
DB_NAME = os.environ["COSMOS_DB_NAME"]
CONTAINER_NAME = os.environ["COSMOS_CONTAINER_NAME"]
# For your container this should be "/userId"
PK_PATH = os.getenv("COSMOS_PARTITION_KEY_PATH", "/userId")

def _pk_field_name(path: str) -> str:
    # Converts "/userId" -> "userId"
    return path.lstrip("/")

def main(myQueueItem: str) -> None:
    logging.info("Queue item received: %s", myQueueItem)
    logging.info("Cosmos: %s / %s | PK path: %s", DB_NAME, CONTAINER_NAME, PK_PATH)

    # Parse message
    try:
        msg = json.loads(myQueueItem)
    except (json.JSONDecodeError, TypeError) as e:
        logging.exception("Queue message is not valid JSON: %s", myQueueItem)
        raise

    # Extract core fields
    action = msg.get("action", "upsert")
    version = msg.get("version", "latest")
    data = msg.get("data") or {}
    doc_id = msg.get("id") or data.get("id")
    if not doc_id:
        raise ValueError("Message must include 'id' or data.id")

    # Build document to write
    document = {**data}
    document["id"] = doc_id
    document["version"] = version

    # Ensure required partition key field is present (e.g., userId)
    pk_field = _pk_field_name(PK_PATH)  # "userId" in your case
    if pk_field not in document:
        # Allow providing PK at top-level, e.g., msg["userId"]
        if pk_field in msg:
            document[pk_field] = msg[pk_field]
        else:
            # If PK is not /id, we must have it explicitly
            if PK_PATH != "/id":
                raise ValueError(
                    f"Missing required partition key field '{pk_field}' for container with PK '{PK_PATH}'. "
                    f"Include it in 'data' or as a top-level field."
                )

    # Connect to Cosmos and write
    client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
    container = client.get_database_client(DB_NAME).get_container_client(CONTAINER_NAME)

    if action == "delete":
        # Use the correct partition key value for delete
        pk_value = document.get(pk_field, document.get("id"))
        container.delete_item(item=document["id"], partition_key=pk_value)
        logging.info("Deleted document: %s (PK %s=%s)", document["id"], pk_field, pk_value)
    else:
        container.upsert_item(document)
        logging.info("Upserted document: %s (PK %s=%s)", document["id"], pk_field, document.get(pk_field))
        
        # Create embedding from content
        if "content" in document:
            try:
                # Truncate content to 8000 chars to avoid embedding API limits
                content_for_embedding = document["content"][:8000]
                
                if not content_for_embedding.strip():
                    logging.warning("Document %s has empty content after truncation", document["id"])
                else:
                    emb = openai_client.embeddings.create(
                        model=os.environ.get("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", "text-embedding-ada-002"),
                        input=content_for_embedding
                    )

                    # Add embedding vector to Cosmos document
                    document["embedding"] = emb.data[0].embedding
                    
                    # Update document with embedding
                    container.upsert_item(document)
                    logging.info("Updated document with embedding: %s", document["id"])
            except Exception as e:
                logging.error("Failed to create embedding for %s: %s", document["id"], str(e))
                # Still keep the document in Cosmos even if embedding fails
        else:
            logging.warning("Document %s has no content field", document["id"])

