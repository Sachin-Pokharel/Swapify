#!/usr/bin/env python3
"""Test script to check camera access in Docker container"""
import cv2
import sys
import os

print("=== Camera Access Test ===")
print(f"Camera index from env: {os.getenv('CAMERA_INDEX', '0')}")

# Check for video devices
import glob
video_devices = glob.glob("/dev/video*")
print(f"\nVideo devices found: {video_devices}")

# Try to open camera
camera_index = int(os.getenv("CAMERA_INDEX", "0"))
print(f"\nAttempting to open camera index {camera_index}...")

try:
    # Try V4L2 backend
    cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
    if not cap.isOpened():
        print("V4L2 backend failed, trying default...")
        cap.release()
        cap = cv2.VideoCapture(camera_index)
    
    if cap.isOpened():
        print("✅ Camera opened successfully!")
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"✅ Successfully read frame: {frame.shape}")
            print("✅ Camera is working!")
        else:
            print("⚠️ Camera opened but failed to read frame")
        cap.release()
    else:
        print("❌ Failed to open camera")
        print("\nTroubleshooting:")
        print("1. Check if /dev/video0 exists in container")
        print("2. Verify docker-compose.yml has device mounted")
        print("3. On Windows: Docker Desktop may not support device passthrough")
        print("4. Try running: docker exec -it swapify_app ls -l /dev/video*")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ Camera test passed!")

