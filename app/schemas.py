from pydantic import BaseModel
from typing import Optional, List

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    username: str
    profile_photo: Optional[str] = None

    class Config:
        from_attributes = True

class FileUploadResponse(BaseModel):
    share_slug: str
    file_type: str

class AccessRequestResponse(BaseModel):
    id: int
    file_id: int
    requester_id: int
    status: str
    duration: Optional[str] = "forever"
    
    class Config:
        from_attributes = True

class PendingRequestResponse(BaseModel):
    request_id: int
    file_name: str
    requester_username: str
    status: str

class FileRenameRequest(BaseModel):
    new_name: str

class FileSearchResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    upload_date: str # Returning as string representation of datetime
    share_slug: Optional[str] = None
    
    class Config:
        from_attributes = True

class AccessRequestCreate(BaseModel):
    owner_id: int
    filename: str
    message: str
    duration: Optional[str] = "forever"
    file_id: Optional[int] = None

class FileChoice(BaseModel):
    id: int
    filename: str
    file_type: str

class MultipleChoicesResponse(BaseModel):
    status: str = "multiple_choices"
    choices: List[FileChoice]

class NotificationResponse(BaseModel):
    id: int
    request_id: int
    requester_username: str
    file_name: str
    message: Optional[str] = None
    created_at: str
    notification_type: str
    
    class Config:
        from_attributes = True

class AccessRespondRequest(BaseModel):
    response: str # 'approved' or 'rejected'
