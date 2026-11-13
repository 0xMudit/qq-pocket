"""Persistent worker for self-hosted beta queues. Set DATABASE_URL."""

import logging
import time
from sqlalchemy.exc import SQLAlchemyError
from app import product

logging.basicConfig(level=logging.INFO)
if __name__ == "__main__":
    while True:
        try:
            result = product.tick(20)
            if result["processed"]:
                logging.info("Processed %s jobs", result["processed"])
        except SQLAlchemyError:
            logging.exception("Database unavailable; retrying")
        time.sleep(1)
