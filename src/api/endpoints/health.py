from fastapi import Request, APIRouter
import logging

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/chat/health")
async def health(request: Request):
    return {"status": "Ok"}
