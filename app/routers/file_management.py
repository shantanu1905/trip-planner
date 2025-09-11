# app/routes/upload.py
import json
import os
from fastapi import APIRouter, UploadFile, Depends , HTTPException
from sqlalchemy.orm import Session
from app.database.database import db_dependency
from app.utils.files_processing import save_file
from starlette import status
from app.utils.auth_helpers import user_dependency
from typing import List


router = APIRouter(tags=['File Management'], prefix="/files")

# @router.post("/upload_files")
# async def upload_file(file: UploadFile, db: db_dependency, user: user_dependency):
#     # 1. Save file
#     file_path = save_file(file)
#     # ✅ calculate file size in bytes
#     size_bytes = os.path.getsize(file_path)

#     # 2. Create Document entry in DB
#     doc = Document(
#         owner_id=user.id,
#         status=ProcessingStatus.queued,
#         filename=file.filename,
#         file_type=file.filename.split(".")[-1],
#         storage_path=file_path,
#         size_bytes=size_bytes,
#     )
#     db.add(doc)
#     db.commit()
#     db.refresh(doc)

#     # 3. Push job to Redis queue
#     job = {"document_id": doc.id, "file_path": file_path}
#     redis_client.rpush(QUEUE_NAME, json.dumps(job))

#     return {"message": "File uploaded and queued for processing", "document_id": doc.id}



# @router.delete("/delete_file/{document_id}")
# async def delete_file(document_id: int, db: db_dependency, user: user_dependency):
#     # 1. Find document
#     doc = db.query(Document).filter(Document.id == document_id, Document.owner_id == user.id).first()
#     if not doc:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Document not found or you don't have permission to delete it"
#         )

#     # 2. Delete file from disk (if exists)
#     if os.path.exists(doc.storage_path):
#         try:
#             os.remove(doc.storage_path)
#         except Exception as e:
#             print(f"⚠️ Could not delete file from disk: {e}")

#     # 3. Delete related Redis chunks
#     pattern = f"doc:{document_id}:chunk:*"
#     for key in redis_client.scan_iter(pattern):
#         redis_client.delete(key)

#     # 4. Delete from DB
#     db.delete(doc)
#     db.commit()

#     return {"message": f"Document {document_id} deleted successfully"}


# @router.post("/upload_files")
# async def upload_file(file: UploadFile, db: db_dependency, user: user_dependency):
#     # 1. Save file
#     file_path = save_file(file)
#     # ✅ calculate file size in bytes
#     size_bytes = os.path.getsize(file_path)

#     # 2. Create Document entry in DB
#     doc = Document(
#         owner_id=user.id,
#         status=ProcessingStatus.queued,
#         filename=file.filename,
#         file_type=file.filename.split(".")[-1],
#         storage_path=file_path,
#         size_bytes=size_bytes,
#     )
#     db.add(doc)
#     db.commit()
#     db.refresh(doc)

#     # 3. Push job to Redis queue
#     job = {"document_id": doc.id, "file_path": file_path}
#     redis_client.rpush(QUEUE_NAME, json.dumps(job))

#     return {"message": "File uploaded and queued for processing", "document_id": doc.id}



# @router.get("/list_files")
# async def list_files(db: db_dependency, user: user_dependency):
#     """
#     List all uploaded documents for the authenticated user.
#     """
#     docs: List[Document] = db.query(Document).filter(Document.owner_id == user.id).all()

#     if not docs:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="No documents found for this user."
#         )

#     return {
#         "documents": [
#             {
#                 "id": doc.id,
#                 "filename": doc.filename,
#                 "status": doc.status.value if doc.status else None,
#                 "file_type": doc.file_type.value if doc.file_type else None,
#                 "size_bytes": doc.size_bytes,
#                 "created_at": doc.created_at,
#                 "error_message": doc.error_message
#             }
#             for doc in docs
#         ]
#     }

