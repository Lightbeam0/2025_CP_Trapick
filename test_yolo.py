import cv2
from ultralytics import YOLO

# Load model
model = YOLO("yolov8n.pt")

video_path = r"C:\Users\naanu\Downloads\D11_20250903090256.mp4"
cap = cv2.VideoCapture(video_path)

# Get video properties
fps = int(cap.get(cv2.CAP_PROP_FPS))
width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# Define codec & create VideoWriter
out = cv2.VideoWriter("output.mp4", cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame)

    # Draw YOLO results on frame
    annotated_frame = results[0].plot()

    # Write the annotated frame into the video
    out.write(annotated_frame)

cap.release()
out.release()
print("✅ Processed video saved as output.mp4")


