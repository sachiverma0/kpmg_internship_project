import os
import json
import uuid
import time
import logging
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI, AzureOpenAI
from jwt import PyJWKClient, decode
from functools import wraps
from azure.cosmos import CosmosClient
from docx import Document
from PyPDF2 import PdfReader

load_dotenv()

# Development mode - disable token validation for local testing
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

print("AZURE_OPENAI_API_KEY:", bool(os.getenv("AZURE_OPENAI_API_KEY")))
print("AZURE_OPENAI_ENDPOINT:", os.getenv("AZURE_OPENAI_ENDPOINT"))
print("AZURE_OPENAI_API_VERSION:", os.getenv("AZURE_OPENAI_API_VERSION"))
print("AZURE_OPENAI_DEPLOYMENT:", os.getenv("AZURE_OPENAI_DEPLOYMENT"))
print("DEV_MODE:", DEV_MODE)

app = Flask(__name__)
CORS(app)

# Optional: limit upload size (e.g., 10 MB)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

# --- Azure OpenAI client (supporting both SDK styles) ---
if os.getenv("AZURE_OPENAI_API_VERSION"):
    # Use AzureOpenAI SDK
    client = AzureOpenAI(
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )
else:
    # Use OpenAI SDK with Azure endpoint
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if endpoint and not endpoint.endswith("/openai/v1"):
        endpoint = endpoint.rstrip("/") + "/openai/v1"
    
    client = OpenAI(
        base_url=endpoint,
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )

# Azure AD Configuration
TENANT_ID = "9f58333b-9cca-4bd9-a7d8-e151e43b79f3"
CLIENT_ID = "a9bda2e7-4cd0-4203-9ae0-62635c58d984"
JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"

# Initialize JWKS client for token validation
jwks_client = PyJWKClient(JWKS_URL)

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

def verify_token(token):
    """Verify and decode Azure AD token"""
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        decoded = decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
        )
        return decoded
    except Exception as e:
        print(f"Token verification failed: {e}")
        return None

def token_required(f):
    """Decorator to require valid token for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip token validation in dev mode
        if DEV_MODE:
            request.user = {"sub": "dev-user", "name": "Dev User", "email": "dev@example.com"}
            return f(*args, **kwargs)
        
        token = None
        
        # Check for token in Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({"error": "Invalid authorization header"}), 401
        
        if not token:
            return jsonify({"error": "Token is missing"}), 401
        
        # Verify token
        decoded = verify_token(token)
        if not decoded:
            return jsonify({"error": "Invalid or expired token"}), 401
        
        # Store decoded token in request context for later use
        request.user = decoded
        return f(*args, **kwargs)
    
    return decorated_function

@app.route("/api/auth/verify", methods=["POST"])
def verify_auth():
    """Endpoint to verify token validity"""
    data = request.get_json()
    token = data.get("token")
    
    if not token:
        return jsonify({"error": "Token is required"}), 400
    
    decoded = verify_token(token)
    if decoded:
        return jsonify({
            "valid": True,
            "user": {
                "name": decoded.get("name"),
                "email": decoded.get("email"),
                "oid": decoded.get("oid")
            }
        }), 200
    else:
        return jsonify({"valid": False, "error": "Token verification failed"}), 401

@app.route("/api/chat", methods=["POST"])
@token_required
def chat():
    """Chat endpoint - requires valid Azure AD token"""
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
        print(f"Error in chat endpoint: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/get-uploaded-files", methods=["GET"])
@token_required
def get_uploaded_files():
    """
    Fetch existing uploaded files for a user.
    Returns both CSV data and policy documents.
    """
    if not container:
        return jsonify({"error": "Cosmos DB not configured"}), 500

    try:
        # Get userId from authenticated user
        user_id = request.user.get("oid") or request.user.get("sub") or "default-user"
        
        # Query for CSV data (get distinct source files).
        csv_query = """
        SELECT DISTINCT c.sourceFile
        FROM c
        WHERE (c.documentType = @csvType OR NOT IS_DEFINED(c.documentType))
          AND IS_DEFINED(c.sourceFile)
          AND c.userId = @userId
        """

        csv_items = list(container.query_items(
            query=csv_query,
            parameters=[
                {"name": "@csvType", "value": "csvData"},
                {"name": "@userId", "value": user_id}
            ],
            enable_cross_partition_query=True
        ))

        # Query for policy documents
        policy_query = """
        SELECT DISTINCT c.fileName, c.uploadedAt
        FROM c
        WHERE c.documentType = @policyType
          AND c.userId = @userId
        """

        policy_items = list(container.query_items(
            query=policy_query,
            parameters=[
                {"name": "@policyType", "value": "policyDocument"},
                {"name": "@userId", "value": user_id}
            ],
            enable_cross_partition_query=True
        ))

        # Format CSV files
        csv_files = [{"name": item.get("sourceFile", "Unknown")} for item in csv_items]

        # Format policy files
        policy_files = [
            {"name": item.get("fileName", "Unknown"), "uploadedAt": item.get("uploadedAt")}
            for item in policy_items
        ]

        return jsonify({"csvFiles": csv_files, "policyFiles": policy_files}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/upload-excel-direct", methods=["POST"])
@token_required
def upload_excel_direct():
    """
    Upload CSV/XLSX and write DIRECTLY to Cosmos DB (bypass queue).
    Deletes existing documents for the user before uploading to prevent data accumulation.
    """
    if not container:
        return jsonify({"error": "Cosmos DB not configured"}), 500

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded (must be 'file')."}), 400

    file = request.files["file"]
    filename = (file.filename or "").lower()
    
    # Get userId from authenticated user
    user_id = request.user.get("oid") or request.user.get("sub") or "default-user"

    try:
        # DELETE EXISTING DOCUMENTS FOR THIS USER FIRST
        try:
            delete_query = "SELECT c.id FROM c WHERE c.userId = @userId AND c.documentType = @docType"
            existing_docs = list(container.query_items(
                query=delete_query,
                parameters=[
                    {"name": "@userId", "value": user_id},
                    {"name": "@docType", "value": "csvData"}
                ],
                enable_cross_partition_query=True
            ))
            
            deleted_count = 0
            for doc in existing_docs:
                container.delete_item(item=doc["id"], partition_key=user_id)
                deleted_count += 1
            
            print(f"Deleted {deleted_count} existing CSV documents for user {user_id}")
        except Exception as del_err:
            print(f"Warning: Failed to delete existing documents: {del_err}")

        # Read CSV file
        if filename.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            return jsonify({"error": "Only .csv files supported."}), 400

        processed_ids = []
        failed_rows = []

        for idx, row in df.iterrows():
            try:
                # Generate ID
                if "id" in df.columns and pd.notna(row.get("id")):
                    row_id = str(row["id"])
                else:
                    row_id = str(uuid.uuid4())

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

                # Build document
                document = {
                    "id": row_id,
                    "userId": user_id,
                    "documentType": "csvData",
                    "title": title,
                    "content": content,
                    "version": "v1",
                    "sourceFile": filename
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
                        time.sleep(0.1)  # Rate limiting
                    except Exception as emb_err:
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


@app.route("/api/upload-policy-documents", methods=["POST"])
@token_required
def upload_policy_documents():
    """
    Upload policy documents (PDF, DOCX, DOC, TXT) and store directly in Cosmos DB.
    Deletes existing policy documents for the user before uploading new ones.
    """
    if not container:
        return jsonify({"error": "Cosmos DB not configured"}), 500

    if "files" not in request.files:
        return jsonify({"error": "No files uploaded (must be 'files')."}), 400

    files = request.files.getlist("files")
    
    # Get userId from authenticated user
    user_id = request.user.get("oid") or request.user.get("sub") or "default-user"

    # DELETE EXISTING POLICY DOCUMENTS FOR THIS USER FIRST
    try:
        delete_query = "SELECT c.id FROM c WHERE c.userId = @userId AND c.documentType = @docType"
        existing_docs = list(container.query_items(
            query=delete_query,
            parameters=[
                {"name": "@userId", "value": user_id},
                {"name": "@docType", "value": "policyDocument"}
            ],
            enable_cross_partition_query=True
        ))
        
        deleted_count = 0
        for doc in existing_docs:
            container.delete_item(item=doc["id"], partition_key=user_id)
            deleted_count += 1
        
        if deleted_count > 0:
            logging.info(f"Deleted {deleted_count} existing policy documents for user {user_id}")
    except Exception as del_err:
        logging.warning(f"Warning: Failed to delete existing policy documents: {del_err}")

    processed_ids = []
    failed_files = []

    for file in files:
        try:
            filename = file.filename or "unknown"
            file_ext = filename.lower().split(".")[-1]

            # Extract text based on file type
            content = None
            if file_ext == "pdf":
                content = extract_text_from_pdf(file)
            elif file_ext in ("docx", "doc"):
                content = extract_text_from_docx(file)
            elif file_ext == "txt":
                content = file.read().decode("utf-8", errors="ignore")
            else:
                failed_files.append(f"{filename}: Unsupported file type. Use PDF, DOCX, DOC, or TXT.")
                continue

            if not content or not content.strip():
                failed_files.append(f"{filename}: No text content found.")
                continue

            # Create document for Cosmos DB
            doc_id = str(uuid.uuid4())
            document = {
                "id": doc_id,
                "userId": user_id,
                "documentType": "policyDocument",
                "title": filename.rsplit(".", 1)[0],
                "content": content,
                "fileName": filename,
                "uploadedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "version": "v1"
            }

            # Write to Cosmos DB
            container.upsert_item(document)

            # Create embedding
            try:
                emb = client.embeddings.create(
                    model=os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"),
                    input=content[:8000]  # Limit to 8000 chars
                )
                document["embedding"] = emb.data[0].embedding
                container.upsert_item(document)
                time.sleep(0.1)
            except Exception as emb_err:
                logging.warning(f"Embedding failed for {filename}: {str(emb_err)}")

            processed_ids.append(doc_id)
            logging.info(f"Successfully processed policy document: {filename}")

        except Exception as file_err:
            failed_files.append(f"{file.filename}: {str(file_err)}")
            logging.error(f"Error processing file {file.filename}: {str(file_err)}")

    return jsonify({
        "status": "completed",
        "filesProcessed": len(processed_ids),
        "filesFailed": len(failed_files),
        "ids": processed_ids,
        "errors": failed_files if failed_files else None
    }), 200


def extract_text_from_pdf(file):
    """Extract text from PDF file."""
    try:
        file.seek(0)
        pdf_reader = PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logging.error(f"PDF extraction error: {str(e)}")
        raise


def extract_text_from_docx(file):
    """Extract text from DOCX/DOC file."""
    try:
        file.seek(0)
        doc = Document(file)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        logging.error(f"DOCX extraction error: {str(e)}")
        raise


@app.route("/api/rag-query", methods=["POST"])
@token_required
def rag_query():
    """RAG query endpoint - uses uploaded documents as context"""
    if not container:
        return jsonify({"error": "Cosmos DB container not initialized."}), 500
    
    data = request.get_json()
    question = data.get("question")
    
    if not question:
        return jsonify({"error": "Question is required"}), 400
    
    # Get userId from authenticated user
    user_id = request.user.get("oid") or request.user.get("sub") or "default-user"

    # Get question embedding
    try:
        qembed = client.embeddings.create(
            model=os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"),
            input=question
        ).data[0].embedding
    except Exception as e:
        return jsonify({"error": f"Embedding failed: {str(e)}"}), 500

    # Query Cosmos DB for user's documents with embeddings
    query = """
    SELECT c.id, c.title, c.content, c.sourceFile, c.fileName
    FROM c
    WHERE IS_DEFINED(c.embedding)
      AND c.userId = @userId
    """

    try:
        items = list(container.query_items(
            query=query,
            parameters=[{"name": "@userId", "value": user_id}],
            enable_cross_partition_query=True
        ))
    except Exception as e:
        return jsonify({"error": f"Cosmos DB query failed: {str(e)}"}), 500

    if not items:
        return jsonify({"error": "No documents with embeddings found. Please upload documents first."}), 400

    # Combine retrieved content with source info
    context_parts = []
    for x in items:
        source = x.get('sourceFile') or x.get('fileName') or x.get('title')
        context_parts.append(f"[Source: {source}]\n{x['content']}")
    context = "\n\n".join(context_parts)

    # Ask GPT with context
    try:
        answer = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            messages=[
                {"role": "system", "content": "You are a RAG assistant. Always cite sources by their filename when referencing information."},
                {"role": "user", "content": f"Question: {question}\n\nContext:\n{context}\n\nAnswer using ONLY the context above. When citing sources, use the [Source: filename] format shown in the context."}
            ]
        ).choices[0].message.content

        return jsonify({"answer": answer, "sources": items})
    except Exception as e:
        return jsonify({"error": f"Chat completion failed: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
