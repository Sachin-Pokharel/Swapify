from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
import io
import numpy as np
import cv2
from app.services.swapper import FaceSwapper

router = APIRouter()
face_swapper = FaceSwapper()


async def read_image_from_upload_file(file: UploadFile):
    try:
        file.file.seek(0)
        contents = await file.read()

        if not contents:
            raise ValueError("Uploaded file is empty")

        np_arr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("cv2.imdecode failed to decode image")

        return image

    except Exception as e:
        print(f"Error reading image: {e}")
        return None



@router.post("/swap-face/")
async def swap_face(
    source_face_file: UploadFile = File(...),
    dest_face_file: UploadFile = File(...),
):
    try:
        # Always await the async read function
        source_image = await read_image_from_upload_file(source_face_file)
        target_image = await read_image_from_upload_file(dest_face_file)

        if source_image is None or target_image is None:
            return {"error": "Failed to read one or both images."}

        source_face = face_swapper.get_face_embedding(source_image)
        if source_face is None:
            return {"error": "No face detected in source image"}

        swapped_img = face_swapper.swap_faces(target_image, source_face)
        success, img_encoded = cv2.imencode(".jpg", swapped_img)

        if not success:
            return {"error": "Failed to encode swapped image"}

        # Convert to bytes
        img_bytes = img_encoded.tobytes()

        # Wrap bytes in a BytesIO stream for StreamingResponse
        img_stream = io.BytesIO(img_bytes)

        return StreamingResponse(content=img_stream, media_type="image/jpeg")
    
    except Exception as e:
        return {"error": f"Something went wrong: {str(e)}"}
