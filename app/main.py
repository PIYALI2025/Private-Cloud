from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import uuid
from datetime import datetime
from typing import Union
from . import models, schemas, securityfeatures, storage_engine, sharinglogic
from .db import engine, get_db
from .logger import get_logger

logger = get_logger(__name__)

# Create the DB tables automatically
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Private Cloud Storage",
    description="A secure, self-hosted file sharing backend",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(FileNotFoundError)
async def file_not_found_handler(request: Request, exc: FileNotFoundError):
    logger.error(f"FileNotFoundError at {request.url}: {exc}")
    return JSONResponse(status_code=404, content={"detail": "File not found on disk"})

@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError):
    logger.error(f"PermissionError at {request.url}: {exc}")
    return JSONResponse(status_code=403, content={"detail": "Permission denied accessing the file"})

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception at {request.url}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

@app.get("/status", summary="Home", description="Root endpoint to check API status.")
def home():
    return {"status": "success", "message": "Day 1 Complete. Models Initialized."}

@app.post("/auth/signup", summary="User Signup", description="Registers a new user account.", response_model=schemas.TokenResponse)
def signup(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
        
    hashed_pwd = securityfeatures.get_password_hash(user_data.password)
    new_user = models.User(username=user_data.username, hashed_password=hashed_pwd)
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token = securityfeatures.create_access_token(data={"sub": new_user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/auth/login", summary="User Login", description="Authenticates user and returns JWT token.", response_model=schemas.TokenResponse)
def login(user_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == user_data.username).first()
    if not user or not securityfeatures.verify_password(user_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for username: {user_data.username}")
        raise HTTPException(status_code=401, detail="Incorrect username or password")
        
    access_token = securityfeatures.create_access_token(data={"sub": user.username})
    logger.info("User logged in successfully", extra={"user_id": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/upload", summary="Upload a File", description="Uploads a file to the vault, extracts metadata, and deduplicates based on content hash.", response_model=schemas.FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    # Read the first 2048 bytes for MIME detection
    header_bytes = await file.read(2048)
    mime_type = storage_engine.get_file_mime_type(header_bytes)
    
    # Calculate file hash for de-duplication
    file_hash = await storage_engine.calculate_file_hash(file)
    
    # Check if this hash already exists in the database
    existing_file = db.query(models.FileMetadata).filter(models.FileMetadata.content_hash == file_hash).first()
    
    # Generate the shared slug specific to this upload event
    new_share_slug = str(uuid.uuid4())[:8]

    # Create the db record linking it to this user
    new_metadata = models.FileMetadata(
        filename=file.filename,
        file_type=mime_type,
        content_hash=file_hash,
        owner_id=current_user.id,
        share_slug=new_share_slug
    )
    
    db.add(new_metadata)
    db.commit()
    db.refresh(new_metadata)
    
    # Local Storage Upload logic
    if not existing_file:
        await storage_engine.save_file_to_disk(file, file_hash)
    
    logger.info(f"File uploaded successfully: {file.filename} with hash {file_hash}", extra={"user_id": current_user.username})
    return {"share_slug": new_metadata.share_slug, "file_type": new_metadata.file_type}

from fastapi.responses import FileResponse
from typing import List, Optional

@app.get("/files/search", summary="Search Files", description="Search through the user's files by name, type, or date.", response_model=List[schemas.FileSearchResponse])
def search_files(
    name: Optional[str] = None,
    file_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    query = db.query(models.FileMetadata).filter(models.FileMetadata.owner_id == current_user.id)
    
    if name:
        query = query.filter(models.FileMetadata.filename.ilike(f"%{name}%"))
    if file_type:
        query = query.filter(models.FileMetadata.file_type.ilike(f"%{file_type}%"))
    if date_from:
        try:
            df = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(models.FileMetadata.created_at >= df)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format, use YYYY-MM-DD")
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d")
            # to include the whole day, perhaps just use >= and <=
            query = query.filter(models.FileMetadata.created_at <= dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format, use YYYY-MM-DD")
            
    files = query.offset(skip).limit(limit).all()
    
    results = []
    for f in files:
        results.append({
            "id": f.id,
            "filename": f.filename,
            "file_type": f.file_type,
            "upload_date": f.created_at.isoformat() if f.created_at else "",
            "share_slug": f.share_slug
        })
    return results

@app.patch("/files/{file_id}/rename", summary="Rename File", description="Renames a file in the user's vault.")
def rename_file(
    file_id: int,
    rename_data: schemas.FileRenameRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    file = db.query(models.FileMetadata).filter(models.FileMetadata.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    if file.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only rename your own files")
        
    file.filename = rename_data.new_name
    db.commit()
    return {"message": "File renamed successfully", "new_name": file.filename}

@app.patch("/files/{file_id}/regenerate-slug", summary="Regenerate Share Link", description="Generates a new shareable slug for the file.")
def regenerate_slug_manual(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    file = db.query(models.FileMetadata).filter(models.FileMetadata.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    if file.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only regenerate slugs for your own files")
        
    new_slug = sharinglogic.regenerate_share_slug(db, file_id)
    return {"message": "Slug regenerated successfully", "new_slug": new_slug}

@app.post("/files/{slug}/request", summary="Request Access", description="Requests access to a file shared by another user.", response_model=schemas.AccessRequestResponse)
def request_access(
    slug: str, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    file = db.query(models.FileMetadata).filter(models.FileMetadata.share_slug == slug).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
        
    if file.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="You already own this file")
        
    existing_req = db.query(models.AccessRequest).filter(
        models.AccessRequest.file_id == file.id,
        models.AccessRequest.requester_id == current_user.id
    ).first()
    
    if existing_req:
        return existing_req
        
    new_req = models.AccessRequest(file_id=file.id, requester_id=current_user.id, status="pending")
    db.add(new_req)
    db.commit()
    db.refresh(new_req)
    return new_req

@app.get("/requests/pending", summary="Get Pending Requests", description="Lists pending access requests for the user's files.", response_model=List[schemas.PendingRequestResponse])
def get_pending_requests(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    requests = db.query(
        models.AccessRequest.id.label("request_id"),
        models.FileMetadata.filename.label("file_name"),
        models.User.username.label("requester_username"),
        models.AccessRequest.status
    ).join(models.FileMetadata, models.FileMetadata.id == models.AccessRequest.file_id)\
     .join(models.User, models.User.id == models.AccessRequest.requester_id)\
     .filter(models.FileMetadata.owner_id == current_user.id, models.AccessRequest.status == "pending")\
     .all()
    
    return [
        {
            "request_id": r.request_id,
            "file_name": r.file_name,
            "requester_username": r.requester_username,
            "status": r.status
        }
        for r in requests
    ]

@app.patch("/requests/{request_id}/{action}", summary="Approve/Deny Request", description="Approves or denies a pending access request.")
def approve_or_deny_request(
    request_id: int, 
    action: str, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    from datetime import timedelta
    if action not in ("approve", "deny"):
        raise HTTPException(status_code=400, detail="Invalid action, must be 'approve' or 'deny'")
        
    access_request = db.query(models.AccessRequest).filter(models.AccessRequest.id == request_id).first()
    if not access_request:
        raise HTTPException(status_code=404, detail="Request not found")
        
    file = db.query(models.FileMetadata).filter(models.FileMetadata.id == access_request.file_id).first()
    if file.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only manage requests for your own files")
        
    # Mark incoming notification as read
    notification = db.query(models.Notification).filter(models.Notification.request_id == request_id).first()
    if notification:
        notification.is_read = True
        
    if action == "approve":
        access_request.status = "approved"
        
        # Calculate expiration
        expires_at = None
        duration = access_request.duration or "forever"
        if duration == "1day":
            expires_at = datetime.utcnow() + timedelta(days=1)
        elif duration == "7days":
            expires_at = datetime.utcnow() + timedelta(days=7)
        elif duration == "1month":
            expires_at = datetime.utcnow() + timedelta(days=30)
        elif duration == "1year":
            expires_at = datetime.utcnow() + timedelta(days=365)
            
        # Grant viewer access via Collaborator
        existing_collab = db.query(models.Collaborator).filter(
            models.Collaborator.file_id == file.id,
            models.Collaborator.user_id == access_request.requester_id
        ).first()
        if existing_collab:
            existing_collab.expires_at = expires_at
            existing_collab.duration = duration
        else:
            new_collab = models.Collaborator(
                file_id=file.id,
                user_id=access_request.requester_id,
                role="viewer",
                expires_at=expires_at,
                duration=duration
            )
            db.add(new_collab)
            
        # Create approved notification for requester
        new_notif = models.Notification(
            user_id=access_request.requester_id,
            request_id=request_id,
            is_read=False,
            notification_type="request_approved",
            custom_message=f"@{current_user.username} approved your request for {file.filename} ({duration})"
        )
        db.add(new_notif)
    else:
        access_request.status = "denied"
        
        # Create denied notification for requester
        new_notif = models.Notification(
            user_id=access_request.requester_id,
            request_id=request_id,
            is_read=False,
            notification_type="request_denied",
            custom_message=f"@{current_user.username} denied your request for {file.filename}"
        )
        db.add(new_notif)
        
    db.commit()
    return {"message": f"Request {access_request.status} successfully"}

@app.get("/download/{slug}", summary="Download File", description="Downloads a file if the user owns it, is a collaborator, or has an approved access request.")
def download_file(
    slug: str, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    """
    Retrieves the file from local vault after efficiently ensuring the user owns it, is a collaborator, or has an approved access request.
    """
    result = db.query(models.FileMetadata, models.AccessRequest.status)\
        .outerjoin(
            models.AccessRequest, 
            (models.AccessRequest.file_id == models.FileMetadata.id) & 
            (models.AccessRequest.requester_id == current_user.id)
        )\
        .filter(models.FileMetadata.share_slug == slug)\
        .first()
    
    if not result:
        raise HTTPException(status_code=404, detail="File not found.")
        
    file_metadata, request_status = result
    
    # Check if user is a collaborator and not expired
    collaborator = db.query(models.Collaborator).filter(
        models.Collaborator.file_id == file_metadata.id,
        models.Collaborator.user_id == current_user.id
    ).first()
    
    is_collaborator = False
    if collaborator:
        if collaborator.expires_at and datetime.utcnow() > collaborator.expires_at:
            db.delete(collaborator)
            db.commit()
        else:
            is_collaborator = True
        
    if file_metadata.owner_id != current_user.id and not is_collaborator:
        if request_status == "pending":
            logger.warning(f"Access denied for file slug {slug} (pending)", extra={"user_id": current_user.username})
            raise HTTPException(status_code=403, detail="403 Forbidden: Access Request Pending")
        elif request_status == "denied":
            logger.warning(f"Access denied for file slug {slug} (denied)", extra={"user_id": current_user.username})
            raise HTTPException(status_code=403, detail="403 Forbidden: Access Request Denied")
        elif request_status != "approved":
            logger.warning(f"Access denied for file slug {slug} (no access)", extra={"user_id": current_user.username})
            raise HTTPException(status_code=403, detail="403 Forbidden: You do not have access to this file. Please request access.")
            
    file_path = storage_engine.VAULT_DIR / file_metadata.content_hash
    
    if not file_path.exists():
        logger.error(f"File not found on disk: {file_path}", extra={"user_id": current_user.username})
        raise HTTPException(status_code=404, detail="File not found on disk.")
        
    try:
        # If the link is ephemeral, regenerate the slug before responding
        if not file_metadata.is_link_permanent:
            sharinglogic.regenerate_share_slug(db, file_metadata.id)
            
        return FileResponse(
            path=file_path, 
            filename=file_metadata.filename, 
            media_type=file_metadata.file_type
        )
    except PermissionError:
        # Handled by global exception handler, but let's let it bubble up or raise
        raise PermissionError(f"Permission error reading file {file_path} from disk.")
    except FileNotFoundError:
        # Handled by global exception handler
        raise FileNotFoundError(f"File {file_path} not found on disk.")
    except Exception as e:
        # Handled by global exception handler
        raise e

# --- New Social & Collaboration Endpoints ---

@app.get("/users/search", summary="Search Users", description="Find users by partial username matches.", response_model=List[schemas.UserResponse])
def search_users(
    q: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    users = db.query(models.User).filter(
        models.User.username.ilike(f"%{q}%"),
        models.User.id != current_user.id
    ).all()
    return users

@app.post("/access/request", summary="Request File Access", description="Request access to a file by filename and owner_id.", response_model=Union[schemas.AccessRequestResponse, schemas.MultipleChoicesResponse])
def request_access_new(
    request_data: schemas.AccessRequestCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    import os
    
    file = None
    if request_data.file_id is not None:
        file = db.query(models.FileMetadata).filter(
            models.FileMetadata.id == request_data.file_id,
            models.FileMetadata.owner_id == request_data.owner_id
        ).first()
        if not file:
            raise HTTPException(status_code=404, detail="Requested file was not found in this user's vault.")
    else:
        # Search all files owned by owner_id to find case-insensitive and extension-independent matches
        owner_files = db.query(models.FileMetadata).filter(models.FileMetadata.owner_id == request_data.owner_id).all()
        matching_files = []
        q_full = request_data.filename.lower()
        q_base = os.path.splitext(request_data.filename)[0].lower()
        
        for f in owner_files:
            f_full = f.filename.lower()
            f_base = os.path.splitext(f.filename)[0].lower()
            if q_full == f_full or q_base == f_base or q_full == f_base:
                matching_files.append(f)
                
        if len(matching_files) == 0:
            raise HTTPException(status_code=404, detail="No matching files found in this user's vault.")
        elif len(matching_files) > 1:
            choices = [{"id": f.id, "filename": f.filename, "file_type": f.file_type} for f in matching_files]
            return {"status": "multiple_choices", "choices": choices}
        else:
            file = matching_files[0]
            
    if file.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="You already own this file.")
        
    existing_req = db.query(models.AccessRequest).filter(
        models.AccessRequest.file_id == file.id,
        models.AccessRequest.requester_id == current_user.id
    ).first()
    
    if existing_req:
        existing_req.message = request_data.message
        existing_req.duration = request_data.duration or "forever"
        db.commit()
        db.refresh(existing_req)
        return existing_req
        
    new_req = models.AccessRequest(
        file_id=file.id, 
        requester_id=current_user.id, 
        status="pending",
        message=request_data.message,
        duration=request_data.duration or "forever"
    )
    db.add(new_req)
    db.commit()
    db.refresh(new_req)
    
    # Create notification for owner
    notification = models.Notification(
        user_id=file.owner_id,
        request_id=new_req.id,
        is_read=False,
        notification_type="request_incoming",
        custom_message=f"@{current_user.username} requested access to {file.filename} ({request_data.duration or 'forever'})"
    )
    db.add(notification)
    db.commit()
    
    return new_req

@app.get("/notifications", summary="Get Notifications", description="Fetch unread access notifications for the user.", response_model=List[schemas.NotificationResponse])
def get_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    notifications = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).all()
    
    response = []
    for n in notifications:
        req = db.query(models.AccessRequest).filter(models.AccessRequest.id == n.request_id).first()
        if not req:
            continue
        file = db.query(models.FileMetadata).filter(models.FileMetadata.id == req.file_id).first()
        if not file:
            continue
            
        if n.notification_type == "request_incoming":
            requester = db.query(models.User).filter(models.User.id == req.requester_id).first()
            sender_name = requester.username if requester else "unknown"
        else:
            owner = db.query(models.User).filter(models.User.id == file.owner_id).first()
            sender_name = owner.username if owner else "unknown"
            
        response.append({
            "id": n.id,
            "request_id": n.request_id,
            "requester_username": sender_name,
            "file_name": file.filename,
            "message": req.message if n.notification_type == "request_incoming" else n.custom_message,
            "created_at": n.created_at.isoformat() if n.created_at else "",
            "notification_type": n.notification_type
        })
        
    return response

@app.patch("/access/respond/{request_id}", summary="Respond to Access Request", description="Approve or deny a pending request.")
def respond_access_request(
    request_id: int,
    respond_data: schemas.AccessRespondRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    from datetime import timedelta
    access_request = db.query(models.AccessRequest).filter(models.AccessRequest.id == request_id).first()
    if not access_request:
        raise HTTPException(status_code=404, detail="Request not found")
        
    file = db.query(models.FileMetadata).filter(models.FileMetadata.id == access_request.file_id).first()
    if file.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only manage requests for your own files")
        
    # Mark incoming notification as read
    notification = db.query(models.Notification).filter(
        models.Notification.request_id == request_id,
        models.Notification.user_id == current_user.id
    ).first()
    if notification:
        notification.is_read = True
        
    if respond_data.response == "approved":
        access_request.status = "approved"
        
        # Calculate expiration
        expires_at = None
        duration = access_request.duration or "forever"
        if duration == "1day":
            expires_at = datetime.utcnow() + timedelta(days=1)
        elif duration == "7days":
            expires_at = datetime.utcnow() + timedelta(days=7)
        elif duration == "1month":
            expires_at = datetime.utcnow() + timedelta(days=30)
        elif duration == "1year":
            expires_at = datetime.utcnow() + timedelta(days=365)
            
        # Grant viewer access via Collaborator
        existing_collab = db.query(models.Collaborator).filter(
            models.Collaborator.file_id == file.id,
            models.Collaborator.user_id == access_request.requester_id
        ).first()
        if existing_collab:
            existing_collab.expires_at = expires_at
            existing_collab.duration = duration
        else:
            new_collab = models.Collaborator(
                file_id=file.id,
                user_id=access_request.requester_id,
                role="viewer",
                expires_at=expires_at,
                duration=duration
            )
            db.add(new_collab)
            
        # Create approved notification for requester
        new_notif = models.Notification(
            user_id=access_request.requester_id,
            request_id=request_id,
            is_read=False,
            notification_type="request_approved",
            custom_message=f"@{current_user.username} approved your request for {file.filename} ({duration})"
        )
        db.add(new_notif)
    else:
        access_request.status = "denied"
        
        # Create denied notification for requester
        new_notif = models.Notification(
            user_id=access_request.requester_id,
            request_id=request_id,
            is_read=False,
            notification_type="request_denied",
            custom_message=f"@{current_user.username} denied your request for {file.filename}"
        )
        db.add(new_notif)
        
    db.commit()
    return {"message": f"Request status updated to {access_request.status}"}

@app.patch("/notifications/{notification_id}/read", summary="Mark Notification as Read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    notif = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"message": "Notification marked as read"}

@app.get("/files/shared", summary="Shared Files", description="List files shared with the user.", response_model=List[schemas.FileSearchResponse])
def get_shared_files(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    # Fetch files where current user is collaborator
    files = db.query(models.FileMetadata)\
        .join(models.Collaborator, models.Collaborator.file_id == models.FileMetadata.id)\
        .filter(models.Collaborator.user_id == current_user.id)\
        .all()
        
    results = []
    for f in files:
        results.append({
            "id": f.id,
            "filename": f.filename,
            "file_type": f.file_type,
            "upload_date": f.created_at.isoformat() if f.created_at else "",
            "share_slug": f.share_slug
        })
    return results

@app.get("/preview/{slug}", summary="Preview File", description="Returns the file for inline viewing (preview) if authorized.")
def preview_file(
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    """
    Retrieves the file for preview, serving it with inline Content-Disposition so the browser can render it directly.
    """
    result = db.query(models.FileMetadata, models.AccessRequest.status)\
        .outerjoin(
            models.AccessRequest, 
            (models.AccessRequest.file_id == models.FileMetadata.id) & 
            (models.AccessRequest.requester_id == current_user.id)
        )\
        .filter(models.FileMetadata.share_slug == slug)\
        .first()
    
    if not result:
        raise HTTPException(status_code=404, detail="File not found.")
        
    file_metadata, request_status = result
    
    collaborator = db.query(models.Collaborator).filter(
        models.Collaborator.file_id == file_metadata.id,
        models.Collaborator.user_id == current_user.id
    ).first()
    
    is_collaborator = False
    if collaborator:
        if collaborator.expires_at and datetime.utcnow() > collaborator.expires_at:
            db.delete(collaborator)
            db.commit()
        else:
            is_collaborator = True
        
    if file_metadata.owner_id != current_user.id and not is_collaborator:
        if request_status == "pending":
            raise HTTPException(status_code=403, detail="403 Forbidden: Access Request Pending")
        elif request_status == "denied":
            raise HTTPException(status_code=403, detail="403 Forbidden: Access Request Denied")
        elif request_status != "approved":
            raise HTTPException(status_code=403, detail="403 Forbidden: You do not have access to this file.")
            
    file_path = storage_engine.VAULT_DIR / file_metadata.content_hash
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk.")
        
    return FileResponse(
        path=file_path,
        media_type=file_metadata.file_type
    )

@app.post("/user/profile-photo", summary="Upload Profile Photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(securityfeatures.get_current_user)
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")
        
    photos_dir = storage_engine.VAULT_DIR / "profile_photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    
    extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    photo_filename = f"{current_user.username}.{extension}"
    photo_path = photos_dir / photo_filename
    
    with open(photo_path, "wb") as f:
        f.write(await file.read())
        
    current_user.profile_photo = photo_filename
    db.commit()
    
    return {"message": "Profile photo uploaded successfully", "profile_photo": photo_filename}

@app.get("/user/profile-photo/{username}", summary="Get Profile Photo")
def get_profile_photo(
    username: str,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not user.profile_photo:
        raise HTTPException(status_code=404, detail="No profile photo set")
        
    photo_path = storage_engine.VAULT_DIR / "profile_photos" / user.profile_photo
    if not photo_path.exists():
        raise HTTPException(status_code=404, detail="Profile photo not found on disk")
        
    return FileResponse(photo_path)

@app.get("/user/me", summary="Get Current User Details", response_model=schemas.UserResponse)
def get_user_me(current_user: models.User = Depends(securityfeatures.get_current_user)):
    return current_user

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")