from fastapi import APIRouter, UploadFile, File, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse
import io
import numpy as np
import cv2
import base64
import json
import asyncio
import logging
from app.services.swapper import FaceSwapper

router = APIRouter()
logger = logging.getLogger(__name__)

# Global variable to store face_swapper instance (will be set from app.state)
face_swapper: FaceSwapper = None


def get_face_swapper(request: Request) -> FaceSwapper:
    """
    Get the FaceSwapper instance from app.state.
    This ensures we use the pre-loaded models from lifespan.
    """
    global face_swapper
    if face_swapper is None:
        # Get from app.state (set during lifespan startup)
        face_swapper = request.app.state.face_swapper_instance
    return face_swapper

# Frame queue management
MAX_QUEUE_SIZE = 2
TARGET_FPS = 12  # 10-15 FPS range
FRAME_INTERVAL = 1.0 / TARGET_FPS


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
    request: Request,
    source_face_file: UploadFile = File(...),
    dest_face_file: UploadFile = File(...),
):
    try:
        # Get face_swapper instance from app.state
        swapper = get_face_swapper(request)
        
        # Always await the async read function
        source_image = await read_image_from_upload_file(source_face_file)
        target_image = await read_image_from_upload_file(dest_face_file)

        if source_image is None or target_image is None:
            return {"error": "Failed to read one or both images."}

        source_face = swapper.get_face_embedding(source_image)
        if source_face is None:
            return {"error": "No face detected in source image"}

        swapped_img = swapper.swap_faces(target_image, source_face)
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


@router.websocket("/swap-face-stream/")
async def swap_face_stream(websocket: WebSocket):
    # Get face_swapper from app.state via websocket's app
    swapper = websocket.app.state.face_swapper_instance
    """
    WebSocket endpoint for real-time face swapping from camera feed.
    Receives base64-encoded frames, processes them, and sends back swapped frames.
    """
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    source_face_embedding = None
    last_frame_time = 0
    frame_queue_size = 0
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            message_type = message.get("type")
            
            if message_type == "source_image":
                # Client sends source image to extract face embedding
                source_image_b64 = message.get("image")
                if source_image_b64:
                    try:
                        # Decode base64 image
                        image_bytes = base64.b64decode(source_image_b64.split(",")[-1])
                        np_arr = np.frombuffer(image_bytes, np.uint8)
                        source_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                        
                        if source_image is not None:
                            source_face_embedding = swapper.get_face_embedding(source_image)
                            if source_face_embedding is not None:
                                await websocket.send_json({
                                    "type": "status",
                                    "status": "ready",
                                    "message": "Source face loaded successfully"
                                })
                                logger.info("Source face embedding loaded")
                            else:
                                await websocket.send_json({
                                    "type": "error",
                                    "message": "No face detected in source image"
                                })
                        else:
                            await websocket.send_json({
                                "type": "error",
                                "message": "Failed to decode source image"
                            })
                    except Exception as e:
                        logger.error(f"Error processing source image: {str(e)}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Error processing source image: {str(e)}"
                        })
                continue
            
            elif message_type == "frame":
                # Client sends camera frame for processing
                current_time = asyncio.get_event_loop().time()
                
                # Frame rate limiting
                if current_time - last_frame_time < FRAME_INTERVAL:
                    continue  # Drop frame if too fast
                
                # Queue management - drop frame if queue is full
                if frame_queue_size > MAX_QUEUE_SIZE:
                    logger.debug(f"Dropping frame - queue size: {frame_queue_size}")
                    continue
                
                frame_queue_size += 1
                last_frame_time = current_time
                
                if source_face_embedding is None:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Source face not loaded. Please send source image first."
                    })
                    frame_queue_size -= 1
                    continue
                
                frame_b64 = message.get("frame")
                if not frame_b64:
                    frame_queue_size -= 1
                    continue
                
                try:
                    # Decode base64 frame
                    image_bytes = base64.b64decode(frame_b64.split(",")[-1])
                    np_arr = np.frombuffer(image_bytes, np.uint8)
                    target_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                    
                    if target_image is None:
                        frame_queue_size -= 1
                        continue
                    
                    # Process face swap
                    swapped_img = swapper.swap_faces(target_image, source_face_embedding)
                    
                    # Encode result to base64
                    success, img_encoded = cv2.imencode(".jpg", swapped_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    
                    if success:
                        img_bytes = img_encoded.tobytes()
                        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
                        
                        # Send back swapped frame
                        await websocket.send_json({
                            "type": "frame",
                            "frame": f"data:image/jpeg;base64,{img_b64}"
                        })
                    
                    frame_queue_size -= 1
                    
                except Exception as e:
                    logger.error(f"Error processing frame: {str(e)}")
                    frame_queue_size -= 1
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Error processing frame: {str(e)}"
                    })
            
            elif message_type == "ping":
                # Keep-alive ping
                await websocket.send_json({"type": "pong"})
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Server error: {str(e)}"
            })
        except:
            pass
