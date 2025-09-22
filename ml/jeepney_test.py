# jeepney_video_advanced.py
from ultralytics import YOLO
import cv2
import os
from pathlib import Path

def advanced_video_detection():
    """Advanced video detection with more options"""
    
    # Load your trained model
    model = YOLO('runs/detect/jeepney_detection/weights/best.pt')
    
    # Input video path (update this to your video path)
    input_video = r"C:/Users/naanu/Downloads/D11_20250903090256.mp4"
    
    # Output directory
    output_dir = "video_results"
    os.makedirs(output_dir, exist_ok=True)
    
    # Get video name for output file
    video_name = Path(input_video).stem
    output_video = os.path.join(output_dir, f"{video_name}_detected.mp4")
    
    # Open video
    cap = cv2.VideoCapture(input_video)
    
    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video, fourcc, fps, (width, height))
    
    print(f"🎬 Processing: {input_video}")
    print(f"📏 Resolution: {width}x{height}")
    print(f"🎞️  FPS: {fps}")
    
    frame_count = 0
    total_jeepneys = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Run inference
        results = model(frame, conf=0.5)  # Confidence threshold
        
        # Annotate frame
        annotated_frame = results[0].plot()
        
        # Count Jeepneys
        jeepney_count = len(results[0].boxes) if results[0].boxes else 0
        total_jeepneys += jeepney_count
        
        # Add counter to frame
        cv2.putText(annotated_frame, f'Frame: {frame_count}', (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(annotated_frame, f'Jeepneys: {jeepney_count}', (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Write frame
        out.write(annotated_frame)
        
        # Display (optional)
        cv2.imshow('Jeepney Detection', annotated_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        
        frame_count += 1
    
    # Cleanup
    cap.release()
    out.release()
    cv2.destroyAllWindows()
    
    print(f"✅ Processing complete!")
    print(f"📹 Output: {output_video}")
    print(f"📊 Total frames: {frame_count}")
    print(f"🚙 Total Jeepneys detected: {total_jeepneys}")
    print(f"📈 Average per frame: {total_jeepneys/max(1, frame_count):.2f}")

if __name__ == "__main__":
    advanced_video_detection()