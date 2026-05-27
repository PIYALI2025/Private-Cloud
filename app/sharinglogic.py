import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException
from . import models

def regenerate_share_slug(db: Session, file_id: int) -> str:
    """
    Regenerates the share_slug for a given file and returns the new slug.
    """
    file_metadata = db.query(models.FileMetadata).filter(models.FileMetadata.id == file_id).first()
    if not file_metadata:
        raise HTTPException(status_code=404, detail="File not found")
        
    new_slug = str(uuid.uuid4())[:8]
    file_metadata.share_slug = new_slug
    db.commit()
    db.refresh(file_metadata)
    
    return new_slug
