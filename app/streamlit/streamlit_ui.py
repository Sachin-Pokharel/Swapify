import streamlit as st
import requests
from io import BytesIO
from PIL import Image

API_URL = "http://127.0.0.1:8000/swap-face/"

def main():
    st.title("Face Swap UI")

    uploaded_source = st.file_uploader("Upload Source Image", type=["jpg", "jpeg", "png"])

    if uploaded_source is not None:
        source_bytes_data = uploaded_source.read()
        source_image = Image.open(BytesIO(source_bytes_data))
        st.image(source_image, caption="Source Image", use_container_width=True)

        uploaded_dest = st.file_uploader("Upload Destination Image", type=["jpg", "jpeg", "png"])

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

                        col1 = st.columns(1)
                        with col1:
                            # Save swapped image button - allows user to download the image
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
