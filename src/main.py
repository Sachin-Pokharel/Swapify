import platform
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
from api.api import api_router


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


if platform.system() == "Windows":
    import pathlib

    pathlib.PosixPath = pathlib.WindowsPath


app = FastAPI(root_path="/api/v1")



# Register routes from the blueprint
app.include_router(api_router)

# Middleware for CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def home(request: Request):
    return {"message": "Face Swapper API"}


@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"
    return response


# Only use this for production / direct run — NOT with reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)