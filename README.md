# Swapify - Face Swapping Application

## Overview

Swapify is a face swapping application that uses deep learning models to swap faces between images. It provides a FastAPI backend for face swapping and a Streamlit UI for easy interaction.

## Project Structure

- `src/services/swapper.py`: Core face swapping logic using InsightFace models.
- `src/api/endpoints/face_swap.py`: FastAPI endpoint to handle face swap requests.
- `src/streamlit/streamlit_ui.py`: Streamlit UI for uploading images and displaying results.
- `model_artifacts/`: Directory to store swapper model files.
- `src/main.py`: Entry point to run the FastAPI server.

## Setup

1. Clone the repository.

2. Place your model inside the `model_artifacts/` directory at the root of the project.

3. Install required Python packages:

```bash
pip install -r requirements.txt
# or manually install
pip install fastapi uvicorn python-multipart insightface streamlit opencv-python pillow requests
```

## Running the Application

### Start the FastAPI Server

Run the FastAPI backend server:

```bash
uvicorn src.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

### Start the Streamlit UI

In a separate terminal, run the Streamlit UI:

```bash
streamlit run src/streamlit/streamlit_ui.py
```

This will open a web interface where you can upload a source image and a destination image, swap faces, and save the result.

## API Endpoint

- `POST /swap-face/`: Accepts two image files (`source_face_file` and `dest_face_file`) and returns the face-swapped image.

## Notes

- Ensure the `python-multipart` package is installed to handle file uploads in FastAPI.
- The face swapping model is loaded from the `model_artifacts` directory for reliable path management.
- The Streamlit UI interacts with the FastAPI backend to perform face swapping.
