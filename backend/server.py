

# server.py
import os
import json
import uuid
import base64
import time
import pandas as pd
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from azure.storage.queue import QueueClient
from azure.cosmos import CosmosClient

# Load env (keeps secrets out of code)
load_dotenv()

# --- Safe startup logs (do not print secrets) ---
print("AZURE_OPENAI_API_KEY set:", bool(os.getenv("AZURE_OPENAI_API_KEY")))
print("AZURE_OPENAI_ENDPOINT:", os.getenv("AZURE_OPENAI_ENDPOINT"))
print("AZURE_OPENAI_DEPLOYMENT:", os.getenv("AZURE_OPENAI_DEPLOYMENT"))

app = Flask(__name__)
# For dev: allow all; for prod, restrict to your frontend origin(s).
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Optional: limit upload size (e.g., 10 MB)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

# --- Azure OpenAI client using OpenAI with Azure endpoint ---
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
if endpoint and not endpoint.endswith("/openai/v1"):
    endpoint = endpoint.rstrip("/") + "/openai/v1"

client = OpenAI(
    base_url=endpoint,
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
)

# --- Initialize QueueClient once (reused across requests) ---
QUEUE_CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
QUEUE_NAME = os.getenv("AZURE_STORAGE_QUEUE_NAME", "myqueue-items")

queue_client = None
if QUEUE_CONN_STR:
    try:
        queue_client = QueueClient.from_connection_string(
            conn_str=QUEUE_CONN_STR, queue_name=QUEUE_NAME
        )
        # Ensure queue exists (idempotent)
        queue_client.create_queue()
        print(f"[Queue] Ready. Using queue: {QUEUE_NAME}")
    except Exception as e:
        print(f"[Queue Init] Warning: {e}")
else:
    print("[Queue Init] No AZURE_STORAGE_CONNECTION_STRING found.")

# --- Initialize Cosmos DB client ---
cosmos_endpoint = os.getenv("COSMOS_ENDPOINT")
cosmos_key = os.getenv("COSMOS_KEY")
cosmos_db_name = os.getenv("COSMOS_DB_NAME")
cosmos_container_name = os.getenv("COSMOS_CONTAINER_NAME")

container = None
if cosmos_endpoint and cosmos_key:
    try:
        cosmos_client = CosmosClient(url=cosmos_endpoint, credential=cosmos_key)
        cosmos_db = cosmos_client.get_database_client(cosmos_db_name)
        container = cosmos_db.get_container_client(cosmos_container_name)
        print(f"[Cosmos] Ready. Using container: {cosmos_container_name}")
    except Exception as e:
        print(f"[Cosmos Init] Warning: {e}")
else:
    print("[Cosmos Init] Missing COSMOS_ENDPOINT or COSMOS_KEY.")

# ---------------------------
# Routes
# ---------------------------

@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(force=True) or {}
        message = data.get("message")
        history = data.get("conversationHistory", [])

        if not message:
            return jsonify({"error": "Missing 'message'"}), 400

        messages = (
            [{"role": "system", "content": "You are a helpful assistant."}]
            + history
            + [{"role": "user", "content": message}]
        )

        completion = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            messages=messages,
            max_completion_tokens=512,
            temperature=0.7,
        )

        text = completion.choices[0].message.content if completion.choices else ""
        return jsonify({"message": text}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ingest", methods=["POST"])
def ingest():
    """
    Accepts JSON and enqueues a single message for the Function to upsert into Cosmos DB.
    Enforces 'userId' because Cosmos container PK is '/userId'.
    """
    if not queue_client:
        return jsonify({"error": "Queue client not configured"}), 500

    try:
        payload = request.get_json(force=True) or {}
        # Expected shape:
        # {
        #   "action": "upsert" | "delete",
        #   "version": "v1",
        #   "userId": "<optional top-level>",
        #   "data": { "id": "doc-123", "title": "...", "content": "...", "userId": "<optional>" }
        # }

        action = payload.get("action", "upsert")
        version = payload.get("version", "latest")
        data = payload.get("data", {}) or {}

        # Resolve id
        message_id = payload.get("id") or data.get("id") or str(uuid.uuid4())

        if action not in ("upsert", "delete"):
            return jsonify({"error": "Invalid action. Use 'upsert' or 'delete'."}), 400

        if action == "delete" and not (payload.get("id") or data.get("id")):
            return jsonify({"error": "Delete requires 'id' or data.id"}), 400

        # === Enforce Cosmos PK '/userId' ===
        user_id = payload.get("userId") or data.get("userId")
        if not user_id:
            return jsonify({
                "error": "Missing required partition key 'userId'. Include it at top-level or inside 'data'."
            }), 400
        # Ensure inside data for the Function to write it to Cosmos
        data["userId"] = user_id

        message = {
            "id": message_id,
            "action": action,
            "version": version,
            "userId": user_id,  # also include at top-level
            "data": data,
        }

        # Send as plain JSON (Azure Queue will handle encoding)
        queue_client.send_message(json.dumps(message))
        return jsonify({"status": "queued", "messageId": message_id}), 202

    except Exception as e:
        return jsonify({"error": str(e)}), 500





@app.route("/api/upload-excel", methods=["POST"])
def upload_excel():
    """
    Accept ANY CSV or XLSX and auto-generate missing fields.
    Makes sure required fields for Cosmos DB exist: id + userId + content/title.
    """
    if not queue_client:
        return jsonify({"error": "Queue client not configured"}), 500

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded (must be 'file')."}), 400

    file = request.files["file"]
    filename = (file.filename or "").lower()

    # Allow user to pass a default userId
    global_userId = request.form.get("userId") or request.args.get("userId")

    try:
        # Read CSV or XLSX
        if filename.endswith(".csv"):
            df = pd.read_csv(file)
        elif filename.endswith(".xlsx"):
            df = pd.read_excel(file, engine="openpyxl")
        else:
            return jsonify({"error": "Only .csv or .xlsx files supported."}), 400

        queued_ids = []

        for _, row in df.iterrows():

            # 1️⃣ AUTO‑GENERATE ID IF MISSING
            if "id" in df.columns and pd.notna(row.get("id")):
                row_id = str(row["id"])
            else:
                row_id = str(uuid.uuid4())

            # 2️⃣ GET USERID (REQUIRED FOR COSMOS PK /userId)
            if "userId" in df.columns and pd.notna(row.get("userId")):
                user_id = str(row["userId"])
            elif global_userId:
                user_id = global_userId
            else:
                return jsonify({
                    "error": (
                        f"Row with auto-id '{row_id}' missing 'userId'. "
                        "Add a userId column or send ?userId=xxxx in upload."
                    )
                }), 400

            # 3️⃣ TITLE AUTO-GENERATION
            if "title" in df.columns and pd.notna(row.get("title")):
                title = str(row["title"])
            else:
                title = f"Record {row_id}"

            # 4️⃣ CONTENT AUTO-GENERATION
            if "content" in df.columns and pd.notna(row.get("content")):
                content = str(row["content"])
            else:
                # Combine all non-empty columns except userId
                content = "\n".join(
                    f"{col}: {row[col]}"
                    for col in df.columns
                    if col != "userId" and pd.notna(row[col])
                )

            # 5️⃣ BUILD QUEUE MESSAGE
            message = {
                "id": row_id,
                "action": "upsert",
                "version": "v1",
                "userId": user_id,
                "data": {
                    "id": row_id,
                    "title": title,
                    "content": content,
                    "userId": user_id
                }
            }

            # Ensure valid JSON serialization
            try:
                message_json = json.dumps(message)
                queue_client.send_message(message_json)
                queued_ids.append(row_id)
            except (TypeError, ValueError) as e:
                logging.error(f"Failed to serialize row {row_id}: {str(e)}")
                return jsonify({
                    "error": f"Row {row_id} contains invalid data for JSON: {str(e)}"
                }), 400

        return jsonify({
            "status": "queued",
            "rowsQueued": len(queued_ids),
            "ids": queued_ids
        }), 202

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/upload-excel-direct", methods=["POST"])
def upload_excel_direct():
    """
    Upload CSV/XLSX and write DIRECTLY to Cosmos DB (bypass queue).
    This avoids queue encoding issues.
    Deletes existing documents for the user before uploading to prevent data accumulation.
    """
    if not container:
        return jsonify({"error": "Cosmos DB not configured"}), 500

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded (must be 'file')."}), 400

    file = request.files["file"]
    filename = (file.filename or "").lower()
    global_userId = request.form.get("userId") or request.args.get("userId")

    try:
        # DELETE EXISTING DOCUMENTS FOR THIS USER FIRST
        if global_userId:
            try:
                delete_query = "SELECT c.id FROM c WHERE c.userId = @userId"
                existing_docs = list(container.query_items(
                    query=delete_query,
                    parameters=[{"name": "@userId", "value": global_userId}],
                    enable_cross_partition_query=True
                ))
                
                deleted_count = 0
                for doc in existing_docs:
                    container.delete_item(item=doc["id"], partition_key=global_userId)
                    deleted_count += 1
                
                print(f"Deleted {deleted_count} existing documents for user {global_userId}")
            except Exception as del_err:
                print(f"Warning: Failed to delete existing documents: {del_err}")

        # Read CSV or XLSX
        if filename.endswith(".csv"):
            df = pd.read_csv(file)
        elif filename.endswith(".xlsx"):
            df = pd.read_excel(file, engine="openpyxl")
        else:
            return jsonify({"error": "Only .csv or .xlsx files supported."}), 400

        processed_ids = []
        failed_rows = []

        for idx, row in df.iterrows():
            try:
                # Generate ID
                if "id" in df.columns and pd.notna(row.get("id")):
                    row_id = str(row["id"])
                else:
                    row_id = str(uuid.uuid4())

                # Get userId
                if "userId" in df.columns and pd.notna(row.get("userId")):
                    user_id = str(row["userId"])
                elif global_userId:
                    user_id = global_userId
                else:
                    failed_rows.append(f"Row {idx}: missing userId")
                    continue

                # Generate title
                if "title" in df.columns and pd.notna(row.get("title")):
                    title = str(row["title"])
                else:
                    title = f"Record {row_id}"

                # Generate content
                if "content" in df.columns and pd.notna(row.get("content")):
                    content = str(row["content"])
                else:
                    content = "\n".join(
                        f"{col}: {row[col]}"
                        for col in df.columns
                        if col != "userId" and pd.notna(row[col])
                    )

                # Build document (no truncation - each row stored separately)
                document = {
                    "id": row_id,
                    "userId": user_id,
                    "title": title,
                    "content": content,
                    "version": "v1",
                    "sourceFile": filename  # Store the filename
                }

                # Write to Cosmos DB
                container.upsert_item(document)

                # Create embedding
                if content.strip():
                    try:
                        emb = client.embeddings.create(
                            model=os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"),
                            input=content
                        )
                        document["embedding"] = emb.data[0].embedding
                        container.upsert_item(document)
                        # Add delay to avoid rate limiting (0.1 seconds between calls)
                        time.sleep(0.1)
                    except Exception as emb_err:
                        # Log embedding errors but continue
                        print(f"[Embedding Error] Row {idx} (ID: {row_id}): {str(emb_err)}")
                        failed_rows.append(f"Row {idx}: embedding failed - {str(emb_err)}")

                processed_ids.append(row_id)

            except Exception as row_err:
                failed_rows.append(f"Row {idx}: {str(row_err)}")

        return jsonify({
            "status": "completed",
            "rowsProcessed": len(processed_ids),
            "rowsFailed": len(failed_rows),
            "ids": processed_ids,
            "errors": failed_rows if failed_rows else None
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# RAG QUERY SETUP
@app.route("/api/rag-query", methods=["POST"])
def rag_query():
    if not container:
        return jsonify({"error": "Cosmos DB container not initialized. Check your COSMOS_* environment variables."}), 500
    
    data = request.get_json()
    question = data["question"]

    # 1. Get question embedding
    qembed = client.embeddings.create(
        model=os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"),
        input=question
    ).data[0].embedding

    # 2. Query Cosmos DB for ALL documents with embeddings
    query = """
    SELECT c.id, c.title, c.content, c.sourceFile
    FROM c
    WHERE IS_DEFINED(c.embedding)
    """

    try:
        items = list(container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
    except Exception as e:
        return jsonify({"error": f"Cosmos DB query failed: {str(e)}"}), 500

    # If no documents with embeddings, return message
    if not items:
        return jsonify({"error": "No documents with embeddings found in Cosmos DB. Please ingest documents first."}), 400

    # 3. Combine retrieved content with source file info
    context_parts = []
    for x in items:
        source = x.get('sourceFile', x['title'])
        context_parts.append(f"[Source: {source}]\n{x['content']}")
    context = "\n\n".join(context_parts)

    # 4. Ask GPT‑4.2 with context
    answer = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": "You are a RAG assistant. Always cite sources by their filename when referencing information."},
            {"role": "user", "content": f"Question: {question}\n\nContext:\n{context}\n\nAnswer using ONLY the context above. When citing sources, use the [Source: filename] format shown in the context."}
        ]
    ).choices[0].message.content

    return jsonify({"answer": answer, "sources": items})


# Entry point
if __name__ == "__main__":
    # Optional: read port from env for cloud hosting compatibility
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
