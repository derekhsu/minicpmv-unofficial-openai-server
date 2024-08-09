import logging
import os
from fastapi import FastAPI
from app.api.v1.api_v1 import router as api_v1_router
from starlette.middleware.cors import CORSMiddleware
import torch
from app.core.minicpm.minicpm_v import MiniCPMVChat
import opencc

logger = logging.getLogger(__name__)

logger = logging.getLogger()
log_format = "[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s"
log_level = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(level=getattr(logging, log_level), format=log_format)

file_handler = logging.FileHandler("app.log")
logger.addHandler(file_handler)

chat_model = MiniCPMVChat("openbmb/MiniCPM-Llama3-V-2_5")
opencc_converter = opencc.OpenCC("s2twp")

import globals
globals.chat_model = chat_model
globals.opencc_converter = opencc_converter

root_path = os.getenv("ROOT_PATH", "")

if os.getenv("PROD_MODE", "false") == 'true':
    logger.info("Run in prod mode")
    app = FastAPI(docs_url=None, redoc_url=None, root_path=root_path)
else:
    logger.info("Run in dev mode")
    app = FastAPI(root_path=root_path)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/v1")
