from dotenv import load_dotenv
import logging
import os

load_dotenv()

_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
	level=getattr(logging, _log_level, logging.INFO),
	format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

