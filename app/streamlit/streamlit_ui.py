import streamlit as st
import requests
from io import BytesIO
from PIL import Image

# Use internal container port since both services run in the same container
# For external access, use host port 6374, but inside container use 8000
import os
API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
API_URL = f"{API_BASE}/api/v1/swap-face/"

def main():
    st.title("Face Swap UI")
    image_swap_mode()

def image_swap_mode():
    """Image swap mode - swap faces between two uploaded images"""
    st.header("Image Face Swap")
    
    uploaded_source = st.file_uploader("Upload Source Image", type=["jpg", "jpeg", "png"], key="img_source")
    
    if uploaded_source is not None:
        source_bytes_data = uploaded_source.read()
        source_image = Image.open(BytesIO(source_bytes_data))
        st.image(source_image, caption="Source Image", use_container_width=True)
        
        uploaded_dest = st.file_uploader("Upload Destination Image", type=["jpg", "jpeg", "png"], key="img_dest")
        
        if uploaded_dest is not None:
            dest_bytes_data = uploaded_dest.read()
            dest_image = Image.open(BytesIO(dest_bytes_data))
            st.image(dest_image, caption="Destination Image", use_container_width=True)
            
            if st.button("Swap Faces"):
                with st.spinner("Swapping faces..."):
                    files = {
                        "source_face_file": (uploaded_source.name, BytesIO(source_bytes_data), uploaded_source.type),
                        "dest_face_file": (uploaded_dest.name, BytesIO(dest_bytes_data), uploaded_dest.type),
                    }
                    
                    response = requests.post(API_URL, files=files)
                    
                    if response.status_code == 200:
                        swapped_image = Image.open(BytesIO(response.content))
                        st.image(swapped_image, caption="Swapped Image", use_container_width=True)
                        
                        # Save swapped image button
                        buf = BytesIO()
                        swapped_image.save(buf, format="JPEG")
                        byte_im = buf.getvalue()
                        
                        st.download_button(
                            label="Save Swapped Image",
                            data=byte_im,
                            file_name="swapped_result.jpg",
                            mime="image/jpeg",
                        )
                    else:
                        st.error(f"Error swapping faces: {response.status_code} - {response.text}")

if __name__ == "__main__":
    main()
