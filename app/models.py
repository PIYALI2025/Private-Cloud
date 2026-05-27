from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from .db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    profile_photo = Column(String, nullable=True)
    
    files = relationship("FileMetadata", back_populates="owner")
    notifications = relationship("Notification", back_populates="user")
    collaborations = relationship("Collaborator", back_populates="user")

class FileMetadata(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    file_type = Column(String)
    content_hash = Column(String, index=True) # For de-duplication
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    # Togglable Link Feature
    share_slug = Column(String, unique=True, default=lambda: str(uuid.uuid4())[:8])
    is_link_permanent = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship("User", back_populates="files")
    collaborators = relationship("Collaborator", back_populates="file")

class AccessRequest(Base):
    __tablename__ = "access_requests"
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"))
    requester_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pending") # pending, approved, denied
    message = Column(String, nullable=True)
    duration = Column(String, default="forever")
    created_at = Column(DateTime, default=datetime.utcnow)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    request_id = Column(Integer, ForeignKey("access_requests.id"))
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    notification_type = Column(String, default="request_incoming")
    custom_message = Column(String, nullable=True)
    
    user = relationship("User", back_populates="notifications")
    access_request = relationship("AccessRequest")

class Collaborator(Base):
    __tablename__ = "collaborators"
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(String, default="viewer")
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    duration = Column(String, default="forever")
    
    user = relationship("User", back_populates="collaborations")
    file = relationship("FileMetadata", back_populates="collaborators")