import os
from .db import SessionLocal
from datetime import datetime
from .models import FileMetadata, Collaborator
from .storage_engine import VAULT_DIR
from .logger import get_logger

logger = get_logger(__name__)

def run_janitor():
    logger.info("Starting Janitor Service...")
    db = SessionLocal()
    
    try:
        # Clean up expired collaborators
        now = datetime.utcnow()
        expired_collabs = db.query(Collaborator).filter(
            Collaborator.expires_at != None,
            Collaborator.expires_at < now
        ).all()
        expired_count = len(expired_collabs)
        for collab in expired_collabs:
            db.delete(collab)
        if expired_count > 0:
            db.commit()
            logger.info(f"Janitor cleaned up {expired_count} expired collaborator permissions.")

        # Get all content hashes from the database
        db_hashes = {f[0] for f in db.query(FileMetadata.content_hash).all()}
        
        # Check files in VAULT_DIR
        if not VAULT_DIR.exists():
            logger.info("Vault directory does not exist. Nothing to clean.")
            return

        deleted_count = 0
        space_saved = 0
        
        for file_path in VAULT_DIR.iterdir():
            if file_path.is_file():
                file_hash = file_path.name
                if file_hash not in db_hashes:
                    # Orphaned file found
                    file_size = file_path.stat().st_size
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        space_saved += file_size
                        logger.info(f"Deleted orphaned file: {file_hash} ({file_size} bytes)")
                    except Exception as e:
                        logger.error(f"Error deleting file {file_hash}: {e}")
                        
        logger.info(f"Janitor Service Complete. Files deleted: {deleted_count}. Space saved: {space_saved / (1024 * 1024):.2f} MB")
        
    finally:
        db.close()

if __name__ == "__main__":
    run_janitor()
