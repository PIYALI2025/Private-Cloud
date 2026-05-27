from app.db import SessionLocal
from app.models import Notification, AccessRequest, FileMetadata, User

db = SessionLocal()

print("--- USERS ---")
for u in db.query(User).all():
    print(f"ID: {u.id}, Username: {u.username}")

print("\n--- FILES ---")
for f in db.query(FileMetadata).all():
    print(f"ID: {f.id}, Filename: {f.filename}, Owner: {f.owner_id}")

print("\n--- ACCESS REQUESTS ---")
for r in db.query(AccessRequest).all():
    print(f"ID: {r.id}, File: {r.file_id}, Requester: {r.requester_id}, Status: {r.status}, Message: {r.message}, Duration: {r.duration}")

print("\n--- NOTIFICATIONS ---")
for n in db.query(Notification).all():
    print(f"ID: {n.id}, User: {n.user_id}, Request: {n.request_id}, IsRead: {n.is_read}, Type: {n.notification_type}, CustomMessage: {n.custom_message}")

db.close()
