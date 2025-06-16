from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
import numpy as np
import cv2
from io import BytesIO
from PIL import Image
from services.swapper import FaceSwapper

router = APIRouter()
face_swapper = FaceSwapper()

def read_imagefile(file) -> np.ndarray:
    image = Image.open(file)
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

@router.post("/swap-face/")
async def swap_face(
    source_face_file: UploadFile = File(...),
    dest_face_file: UploadFile = File(...),
):
    # Read images from uploaded files
    source_img = read_imagefile(source_face_file.file)
    dest_img = read_imagefile(dest_face_file.file)

    # Get face embeddings
    source_face = face_swapper.get_face_embedding(source_img)
    if source_face is None:
        return {"error": "No face detected in source image"}

    dest_face = face_swapper.get_face_embedding(dest_img)
    if dest_face is None:
        return {"error": "No face detected in destination image"}

    # Swap faces using both embeddings
    swapped_img = face_swapper.swap_faces(dest_img, source_face, dest_face)

    # Convert result to JPEG bytes
    _, img_encoded = cv2.imencode('.jpg', swapped_img)
    return StreamingResponse(BytesIO(img_encoded.tobytes()), media_type="image/jpeg")
