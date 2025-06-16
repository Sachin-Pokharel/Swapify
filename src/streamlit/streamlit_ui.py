import streamlit as st
import requests
from io import BytesIO
from PIL import Image

API_URL = "http://127.0.0.1:8000/swap-face/"

def main():
    st.title("Face Swap UI")

    uploaded_source = st.file_uploader("Upload Source Image", type=["jpg", "jpeg", "png"])
    source_image = None
    dest_image = None

    if uploaded_source is not None:
        source_image = Image.open(uploaded_source)
        st.image(source_image, caption="Source Image", use_container_width=True)

        uploaded_dest = st.file_uploader("Upload Destination Image", type=["jpg", "jpeg", "png"])
        if uploaded_dest is not None:
            dest_image = Image.open(uploaded_dest)
            st.image(dest_image, caption="Destination Image", use_container_width=True)

    if source_image and dest_image:
        if st.button("Swap Faces"):
            with st.spinner("Swapping faces..."):
                files = {
                    "source_face_file": (uploaded_source.name, uploaded_source, uploaded_source.type),
                    "dest_face_file": (uploaded_dest.name, uploaded_dest, uploaded_dest.type),
                }
                response = requests.post(API_URL, files=files)
                if response.status_code == 200:
                    swapped_image = Image.open(BytesIO(response.content))
                    st.image(swapped_image, caption="Swapped Image", use_container_width=True)
                    if st.button("Save Swapped Image"):
                        swapped_image.save("swapped_result.jpg")
                        st.success("Image saved as swapped_result.jpg")
                else:
                    st.error(f"Error swapping faces: {response.text}")

if __name__ == "__main__":
    main()
