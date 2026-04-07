import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI

from app.api import health, webhook
from app.core.config import config

# Setup logging
log_file = config.log_file
log_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=10)
logging.basicConfig(
    handlers=[log_handler, logging.StreamHandler()],
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logging.info("Avanpost starting up...")
    yield
    # Shutdown logic (if needed)
    logging.info("Avanpost shutting down...")


app = FastAPI(title="Avanpost Deployment Engine", lifespan=lifespan)

# Include Routers
app.include_router(webhook.router)
app.include_router(health.router)
