import gradio as gr
import requests
import os
from PIL import Image
import io
import tempfile
import logging
import traceback
import base64
import json
import asyncio
import websockets
import threading
from typing import Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API endpoint - same as streamlit
API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
API_URL = f"{API_BASE}/api/v1/swap-face/"

# WebSocket endpoint
WS_BASE = os.getenv("API_BASE_URL", "ws://127.0.0.1:8000").replace("http://", "ws://").replace("https://", "wss://")
WS_URL = f"{WS_BASE}/api/v1/swap-face-stream/"

# Global variables for WebSocket connection
websocket_connection: Optional[websockets.WebSocketClientProtocol] = None
source_image_loaded = False

# Frame queue management
frame_queue_size = 0
last_frame_time = 0
FRAME_INTERVAL = 1.0 / 12  # ~12 FPS (10-15 FPS range)
MAX_QUEUE_SIZE = 2


def pil_to_bytes(image: Image.Image, format: str = "JPEG") -> bytes:
    """Convert PIL Image to bytes"""
    buffered = io.BytesIO()
    image.save(buffered, format=format)
    return buffered.getvalue()


def swap_images(source_image: Image.Image, dest_image: Image.Image):
    """Swap faces between two images"""
    if source_image is None:
        return None, None, "Please upload a source image first."
    
    if dest_image is None:
        return None, None, "Please upload a destination image first."
    
    try:
        # Convert PIL images to bytes
        source_bytes = pil_to_bytes(source_image)
        dest_bytes = pil_to_bytes(dest_image)
        
        # Prepare files for API request
        files = {
            "source_face_file": ("source.jpg", source_bytes, "image/jpeg"),
            "dest_face_file": ("dest.jpg", dest_bytes, "image/jpeg"),
        }
        
        # Call API
        response = requests.post(API_URL, files=files, timeout=60)
        response.raise_for_status()
        
        # Convert response to PIL Image
        swapped_image = Image.open(io.BytesIO(response.content))
        
        # Create temporary file for download
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
            swapped_image.save(tmp_file.name, format="JPEG")
            swapped_file = tmp_file.name
        
        return swapped_image, swapped_file, None
        
    except requests.exceptions.RequestException as e:
        error_msg = f"API Error: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                error_msg += f"\n\nError details: {error_detail}"
            except:
                error_msg += f"\n\nError response: {e.response.text}"
        return None, None, error_msg
    except Exception as e:
        return None, None, f"Error: {str(e)}"


async def _connect_websocket_internal():
    """Internal async function to connect WebSocket (must be called from dedicated loop)"""
    global websocket_connection
    try:
        # Check if connection exists and is still open
        if websocket_connection is None:
            websocket_connection = await websockets.connect(WS_URL)
            logger.info(f"WebSocket connected to {WS_URL}")
        else:
            # Try to check if connection is still alive by sending a ping
            try:
                await websocket_connection.ping()
            except:
                # Connection is dead, reconnect
                try:
                    await websocket_connection.close()
                except:
                    pass
                websocket_connection = await websockets.connect(WS_URL)
                logger.info(f"WebSocket reconnected to {WS_URL}")
        return True
    except Exception as e:
        logger.error(f"Failed to connect WebSocket: {str(e)}")
        websocket_connection = None
        return False


def connect_websocket_sync():
    """Synchronous wrapper to connect WebSocket"""
    loop = get_or_create_loop()
    future = asyncio.run_coroutine_threadsafe(_connect_websocket_internal(), loop)
    try:
        return future.result(timeout=5)
    except Exception as e:
        logger.error(f"Error connecting WebSocket: {str(e)}")
        return False


async def _disconnect_websocket_internal():
    """Internal async function to disconnect WebSocket (must be called from dedicated loop)"""
    global websocket_connection
    try:
        if websocket_connection is not None:
            try:
                await websocket_connection.close()
                logger.info("WebSocket disconnected")
            except:
                pass
            websocket_connection = None
    except Exception as e:
        logger.error(f"Error disconnecting WebSocket: {str(e)}")
        websocket_connection = None


async def _send_source_image_internal(source_image: Image.Image):
    """Internal async function to send source image (must be called from dedicated loop)"""
    global source_image_loaded, websocket_connection
    
    if source_image is None:
        return False, "No source image provided"
    
    try:
        # Ensure WebSocket is connected
        if not await _connect_websocket_internal():
            return False, "Failed to connect to WebSocket"
        
        # Convert PIL image to base64
        img_bytes = pil_to_bytes(source_image)
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        
        # Send source image
        message = {
            "type": "source_image",
            "image": f"data:image/jpeg;base64,{img_b64}"
        }
        
        if websocket_connection is None:
            return False, "WebSocket connection not available"
        
        await websocket_connection.send(json.dumps(message))
        response = await websocket_connection.recv()
        response_data = json.loads(response)
        
        if response_data.get("type") == "status" and response_data.get("status") == "ready":
            source_image_loaded = True
            return True, "Source face loaded successfully"
        elif response_data.get("type") == "error":
            return False, response_data.get("message", "Unknown error")
        else:
            return False, "Unexpected response from server"
            
    except Exception as e:
        logger.error(f"Error sending source image: {str(e)}")
        return False, f"Error: {str(e)}"


async def _process_frame_websocket_internal(frame_image: Image.Image):
    """Internal async function to process frame (must be called from dedicated loop)"""
    global websocket_connection, source_image_loaded
    
    if not source_image_loaded:
        return None, "Source image not loaded. Please upload source image first."
    
    if frame_image is None:
        return None, None
    
    try:
        # Ensure WebSocket is connected
        if not await _connect_websocket_internal():
            return None, "WebSocket not connected"
        
        if websocket_connection is None:
            return None, "WebSocket connection not available"
        
        # Convert PIL image to base64
        img_bytes = pil_to_bytes(frame_image)
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        
        # Send frame
        message = {
            "type": "frame",
            "frame": f"data:image/jpeg;base64,{img_b64}"
        }
        
        await websocket_connection.send(json.dumps(message))
        response = await websocket_connection.recv()
        response_data = json.loads(response)
        
        if response_data.get("type") == "frame":
            # Decode base64 response
            frame_b64 = response_data.get("frame", "").split(",")[-1]
            frame_bytes = base64.b64decode(frame_b64)
            swapped_image = Image.open(io.BytesIO(frame_bytes))
            return swapped_image, None
        elif response_data.get("type") == "error":
            return None, response_data.get("message", "Unknown error")
        else:
            return None, "Unexpected response from server"
            
    except Exception as e:
        logger.error(f"Error processing frame: {str(e)}")
        return None, f"Error: {str(e)}"


# Shared event loop for WebSocket operations
_websocket_loop = None
_websocket_loop_thread = None

def get_or_create_loop():
    """Get or create a dedicated event loop for WebSocket operations"""
    global _websocket_loop, _websocket_loop_thread
    
    if _websocket_loop is None or _websocket_loop.is_closed():
        def run_loop():
            global _websocket_loop
            _websocket_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_websocket_loop)
            _websocket_loop.run_forever()
        
        _websocket_loop_thread = threading.Thread(target=run_loop, daemon=True)
        _websocket_loop_thread.start()
        # Wait a bit for loop to start
        import time
        time.sleep(0.1)
    
    return _websocket_loop


# Wrapper functions for Gradio (Gradio doesn't support async directly)
def send_source_image_sync(source_image: Image.Image):
    """Synchronous wrapper for sending source image"""
    loop = get_or_create_loop()
    future = asyncio.run_coroutine_threadsafe(_send_source_image_internal(source_image), loop)
    try:
        success, message = future.result(timeout=10)
        return success, message
    except Exception as e:
        logger.error(f"Error in send_source_image_sync: {str(e)}")
        return False, f"Error: {str(e)}"


def process_frame_sync(frame_image: Image.Image):
    """Synchronous wrapper for processing frame"""
    loop = get_or_create_loop()
    future = asyncio.run_coroutine_threadsafe(_process_frame_websocket_internal(frame_image), loop)
    try:
        result, error = future.result(timeout=5)
        return result, error
    except Exception as e:
        logger.error(f"Error in process_frame_sync: {str(e)}")
        return None, f"Error: {str(e)}"


# Custom CSS with Geist font and #007aff color scheme
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --primary-color: #007aff;
    --primary-dark: #0051d5;
    --primary-light: #5ac8fa;
    --primary-lighter: #e3f2fd;
    --gradient-start: #00d4ff;
    --gradient-end: #7b2ff7;
    --card-bg: #ffffff;
    --card-shadow: rgba(0, 0, 0, 0.1);
}

* {
    font-family: 'Inter', 'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.gradio-container {
    font-family: 'Inter', 'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: linear-gradient(135deg, #e3f2fd 0%, #ffffff 100%) !important;
    min-height: 100vh;
    padding: 1rem 2rem !important;
}

h1, .heading h1 {
    background: linear-gradient(135deg, var(--primary-color) 0%, var(--gradient-end) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 700 !important;
    font-size: 2.5rem !important;
    margin: 0.5rem 0 1rem 0 !important;
    padding: 0 !important;
    text-align: center;
    display: block !important;
    visibility: visible !important;
}

/* Ensure markdown headings are visible */
.markdown h1 {
    background: linear-gradient(135deg, var(--primary-color) 0%, var(--gradient-end) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 700 !important;
    font-size: 2.5rem !important;
    margin: 0.5rem 0 1rem 0 !important;
    padding: 0 !important;
    text-align: center;
    display: block !important;
    visibility: visible !important;
}

/* Card styling */
.panel, .form, .output {
    background: var(--card-bg) !important;
    border-radius: 16px !important;
    padding: 2rem !important;
    box-shadow: 0 4px 20px var(--card-shadow) !important;
    border: 1px solid rgba(0, 122, 255, 0.1) !important;
}

/* Section headings */
h2, h3 {
    color: #333 !important;
    font-weight: 600 !important;
    margin-bottom: 1.5rem !important;
    font-size: 1.5rem !important;
}

/* Image upload area styling */
.upload-area, .image-container {
    border: 2px dashed !important;
    border-image: linear-gradient(135deg, var(--gradient-start), var(--gradient-end)) 1 !important;
    border-radius: 12px !important;
    background: linear-gradient(135deg, rgba(0, 212, 255, 0.05), rgba(123, 47, 247, 0.05)) !important;
    padding: 1rem !important;
    min-height: 400px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

/* Make uploaded images larger */
img {
    max-width: 100% !important;
    max-height: 500px !important;
    object-fit: contain !important;
}

/* Image preview container */
.image-preview {
    width: 100% !important;
    height: auto !important;
    max-height: 500px !important;
}

/* Dropdown styling */
select, .dropdown {
    border-radius: 8px !important;
    border: 1px solid rgba(0, 122, 255, 0.2) !important;
    padding: 0.75rem !important;
}

/* Submit button with gradient */
button.primary {
    background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%) !important;
    border: none !important;
    border-radius: 8px !important;
    color: white !important;
    font-weight: 600 !important;
    padding: 0.75rem 2rem !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 15px rgba(0, 122, 255, 0.3) !important;
}

button.primary:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(0, 122, 255, 0.4) !important;
}

/* Row and column spacing */
.gr-row {
    gap: 2rem !important;
}

.gr-column {
    gap: 1.5rem !important;
}

/* Label styling */
label {
    font-weight: 600 !important;
    color: #333 !important;
    margin-bottom: 0.5rem !important;
}

.prose {
    color: #666 !important;
    text-align: center;
    margin: 0.5rem 0 1.5rem 0 !important;
    padding: 0 !important;
}

/* Reduce spacing in main container */
.main {
    padding-top: 0.5rem !important;
}

/* Card styling - reduce padding */
.panel, .form, .output {
    background: var(--card-bg) !important;
    border-radius: 16px !important;
    padding: 1.5rem !important;
    box-shadow: 0 4px 20px var(--card-shadow) !important;
    border: 1px solid rgba(0, 122, 255, 0.1) !important;
    margin-top: 0 !important;
}
"""


# Create Gradio interface
with gr.Blocks() as demo:
    # Heading - make it prominent
    gr.Markdown(
        "<h1 style='background: linear-gradient(135deg, #007aff 0%, #7b2ff7 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-weight: 700; font-size: 2.5rem; margin: 0.5rem 0 1rem 0; padding: 0; text-align: center;'>Face Swapper Playground</h1>",
        elem_classes=["heading"]
    )
    
    gr.Markdown(
        "Swap faces between images or use live camera feed to see face swaps in real-time.",
        elem_classes=["prose"]
    )
    
    # Create tabs for different modes
    with gr.Tabs():
        # Tab 1: Image Swap
        with gr.Tab("Image Swap"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Upload Images")
                    
                    source_image = gr.Image(
                        label="Source Image",
                        type="pil",
                        height=300,
                        show_label=True
                    )
                    
                    dest_image = gr.Image(
                        label="Destination Image",
                        type="pil",
                        height=300,
                        show_label=True
                    )
                    
                    swap_btn = gr.Button(
                        "Swap Faces",
                        variant="primary",
                        size="lg"
                    )
                
                with gr.Column(scale=1):
                    gr.Markdown("### Swapped Result")
                    
                    swapped_output = gr.Image(
                        label="",
                        type="pil",
                        height=500,
                        show_label=False
                    )
                    
                    error_output = gr.Textbox(
                        label="",
                        lines=3,
                        max_lines=5,
                        placeholder="",
                        show_label=False,
                        visible=False
                    )
                    
                    save_btn = gr.File(
                        label="Download Swapped Image",
                        visible=False
                    )
            
            # Connect swap button
            def swap_and_update(source_img, dest_img):
                """Swap images and update all outputs"""
                img, file, err = swap_images(source_img, dest_img)
                if err:
                    return (
                        None,
                        gr.update(visible=False),
                        gr.update(value=err, visible=True)
                    )
                else:
                    return (
                        img,
                        gr.update(value=file, visible=True),
                        gr.update(visible=False)
                    )
            
            swap_btn.click(
                fn=swap_and_update,
                inputs=[source_image, dest_image],
                outputs=[swapped_output, save_btn, error_output]
            )
        
        # Tab 2: Camera Feed
        with gr.Tab("Camera Feed"):
            gr.Markdown(
                "**Instructions:** Upload a source image, then enable your webcam. Face swapping happens in real-time via WebSocket!",
                elem_classes=["prose"]
            )
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Setup")
                    
                    source_image_camera = gr.Image(
                        label="Source Image (Face to Swap)",
                        type="pil",
                        height=300,
                        show_label=True
                    )
                    
                    connection_status = gr.Textbox(
                        label="Connection Status",
                        value="Upload source image to begin.",
                        interactive=False,
                        show_label=True
                    )
                    
                    gr.Markdown("### Live Camera Feed")
                    
                    camera_input = gr.Image(
                        label="Camera (Click to enable webcam)",
                        type="pil",
                        sources=["webcam"],
                        height=400,
                        show_label=True
                    )
                
                with gr.Column(scale=1):
                    gr.Markdown("### Live Swapped Result")
                    gr.Markdown(
                        "*The face-swapped video feed will appear here in real-time via WebSocket.*",
                        elem_classes=["prose"]
                    )
                    
                    swapped_camera_output = gr.Image(
                        label="Live Face-Swapped Feed",
                        type="pil",
                        height=400,
                        show_label=True
                    )
                    
                    error_camera_output = gr.Textbox(
                        label="Errors",
                        lines=5,
                        max_lines=10,
                        placeholder="",
                        show_label=True,
                        visible=False
                    )
            
            with gr.Row():
                with gr.Column():
                    # Debug info display
                    debug_output = gr.Textbox(
                        label="Debug Logs (Real-time processing information)",
                        lines=10,
                        max_lines=15,
                        placeholder="Debug information will appear here as frames are processed...",
                        show_label=True,
                        interactive=False
                    )
            
            def handle_source_image(source_img):
                """Handle source image upload - send to WebSocket"""
                if source_img is None:
                    return (
                        gr.update(value="Please upload a source image."),
                        gr.update(visible=False),
                        "No source image provided."
                    )
                
                success, message = send_source_image_sync(source_img)
                
                if success:
                    return (
                        gr.update(value="✅ Source face loaded! Enable webcam to start."),
                        gr.update(visible=False),
                        f"✓ {message}"
                    )
                else:
                    return (
                        gr.update(value=f"❌ Error: {message}"),
                        gr.update(value=message, visible=True),
                        f"Error: {message}"
                    )
            
            def process_camera_frame(source_img, camera_frame):
                """Process camera frame through WebSocket with frame dropping"""
                global frame_queue_size, last_frame_time
                
                import time as time_module
                current_time = time_module.time()
                
                # Check if source image is loaded
                if not source_image_loaded:
                    if source_img is None:
                        return None, None, "Please upload a source image first."
                    # Try to load source image
                    success, msg = send_source_image_sync(source_img)
                    if not success:
                        return None, None, f"Failed to load source image: {msg}"
                
                if camera_frame is None:
                    return None, None, "Enable your webcam to see face swap."
                
                # Frame rate limiting - drop if too fast
                if current_time - last_frame_time < FRAME_INTERVAL:
                    return None, None, "Frame rate limited (12 FPS max)"
                
                # Queue management - drop frame if queue is full
                if frame_queue_size > MAX_QUEUE_SIZE:
                    return None, None, f"Dropping frame - queue full ({frame_queue_size})"
                
                frame_queue_size += 1
                last_frame_time = current_time
                
                try:
                    # Process frame through WebSocket
                    swapped_frame, error = process_frame_sync(camera_frame)
                    frame_queue_size -= 1
                    
                    if error:
                        debug_info = f"Error: {error}"
                        return None, gr.update(value=error, visible=True), debug_info
                    else:
                        debug_info = (
                            f"✓ Frame processed successfully\n"
                            f"Queue size: {frame_queue_size}\n"
                            f"FPS: ~12 (rate limited)\n"
                            f"Source: Loaded\n"
                            f"Status: Active"
                        )
                        return swapped_frame, gr.update(visible=False), debug_info
                        
                except Exception as e:
                    frame_queue_size -= 1
                    error_msg = f"Processing error: {str(e)}"
                    logger.error(error_msg)
                    return None, gr.update(value=error_msg, visible=True), f"Error: {error_msg}"
            
            # Connect events
            source_image_camera.change(
                fn=handle_source_image,
                inputs=[source_image_camera],
                outputs=[connection_status, error_camera_output, debug_output]
            )
            
            # Process camera frames when webcam updates
            camera_input.change(
                fn=process_camera_frame,
                inputs=[source_image_camera, camera_input],
                outputs=[swapped_camera_output, error_camera_output, debug_output]
            )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        css=custom_css,
        theme=gr.themes.Soft(primary_hue="blue")
    )
