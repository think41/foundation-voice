import os
import json
from loguru import logger

def save_conversation_data(data):
    """
    Save conversation data to the filesystem for history.
    """
    if os.getenv("CONVERSATION_HISTORY") == "true" and os.getenv("CONVERSATION_DIR") is not None:
        CONVERSATIONS_DIR = os.getenv("CONVERSATION_DIR")
    else:
        return False;
        
    if not os.path.exists(CONVERSATIONS_DIR):
        os.makedirs(CONVERSATIONS_DIR)
        
    try:
        logger.info("Starting to save conversation data")
        sessionid = data.get("sessionid") or data.get("metrics", {}).get("sessionid")
        if not sessionid:
            from datetime import datetime
            sessionid = f"session_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            logger.debug(f"Generated new session ID: {sessionid}")
        
        logger.debug(f"Creating conversation record for session {sessionid}")
        conversation_record = {
            "sessionid": sessionid,
            "metadata": data.get("metadata", {}),
            "transcript": data.get("transcript", []),
            "metrics": data.get("metrics", {})
        }
        
        fpath = os.path.join(CONVERSATIONS_DIR, f"{sessionid}.json")
        logger.debug(f"Writing conversation to file: {fpath}")
        with open(fpath, "w") as f:
            json.dump(conversation_record, f, indent=2)
        
        logger.info(f"Successfully saved conversation to {fpath}")
        return True
    except Exception as e:
        logger.error(f"Error saving conversation to filesystem: {str(e)}")
        logger.exception("Full exception details:")
        return False