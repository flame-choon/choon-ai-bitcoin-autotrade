from fastapi import APIRouter
from core.response import ResponseHandler

router = APIRouter()

@router.get("/health")
async def health_check():
    return ResponseHandler.success({
        "status": "healthy",
        "message": "Service is running"
    })

@router.get("/")
async def root():
    return ResponseHandler.success({
        "message": "This is a project for batch processing in Choon Autotrade."
    })