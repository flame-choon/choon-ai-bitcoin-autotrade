import logging
from datetime import datetime

class Log:

    INFO = 1
    WARNING = 2
    ERROR = 3

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    def recordLog(self, type, title, contents):
        if type == Log.INFO:
            logging.info(f"[{datetime.now()}] {title} : {contents}")
        elif type == Log.WARNING:
            logging.warning(f"[{datetime.now()}] {title} : {contents}")
        elif type == Log.ERROR:
            logging.error(f"[{datetime.now()}] {title} : {contents}")
        else:
            logging.info(f"[{datetime.now()}] {title} : {contents}")