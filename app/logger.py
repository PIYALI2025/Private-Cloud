import logging
import sys

# Define the custom log format
LOG_FORMAT = "[%(asctime)s] %(levelname)s - User: %(user_id)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

class UserLoggerAdapter(logging.LoggerAdapter):
    """
    An adapter that injects 'user_id' into log records.
    If 'user_id' is passed in extra kwargs, it overrides the default.
    """
    def process(self, msg, kwargs):
        # Allow passing user_id at the log call level
        extra = kwargs.get("extra", {})
        if "user_id" not in extra:
            extra["user_id"] = self.extra.get("user_id", "SYSTEM") if self.extra else "SYSTEM"
        kwargs["extra"] = extra
        return msg, kwargs

def get_logger(name: str) -> UserLoggerAdapter:
    logger = logging.getLogger(name)
    # Initialize with default extra dict
    return UserLoggerAdapter(logger, {"user_id": "SYSTEM"})
