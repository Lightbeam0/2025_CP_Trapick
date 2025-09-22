# merged_detection.py
from ultralytics import YOLO
import cv2
import numpy as np

class CombinedDetector:
    def __init__(self):
        # Load both models
        self.coco_model = YOLO('yolov8n.pt')  # Original COCO model
        self.jeepney_model = YOLO('runs/detect/jeepney_detection/weights/best.pt')  # Your Jeepney model
        
        # Combined class names (COCO + Jeepney)
        self.class_names = self.coco_model.names.copy()
        self.class_names[80] = 'Jeepney'  # Add Jeepney as class 80
        
    def detect_combined(self, image_path, conf_threshold=0.5):
        """Run both models and combine results"""
        
        # Run both detections
        coco_results = self.coco_model(image_path, conf=conf_threshold)
        jeepney_results = self.jeepney_model(image_path, conf=conf_threshold)
        
        # Get detections from both models
        all_detections = []
        
        # Add COCO detections
        if coco_results[0].boxes is not None:
            for box in coco_results[0].boxes:
                detection = {
                    'class_id': int(box.cls.item()),
                    'class_name': self.class_names[int(box.cls.item())],
                    'confidence': float(box.conf.item()),
                    'bbox': box.xyxy[0].tolist()
                }
                all_detections.append(detection)
        
        # Add Jeepney detections (map to class ID 80)
        if jeepney_results[0].boxes is not None:
            for box in jeepney_results[0].boxes:
                detection = {
                    'class_id': 80,  # Custom ID for Jeepney
                    'class_name': 'Jeepney',
                    'confidence': float(box.conf.item()),
                    'bbox': box.xyxy[0].tolist()
                }
                all_detections.append(detection)
        
        return all_detections
    
    def visualize_detections(self, image_path, detections, output_path='combined_result.jpg'):
        """Visualize combined detections"""
        
        image = cv2.imread(image_path)
        
        for detection in detections:
            x1, y1, x2, y2 = map(int, detection['bbox'])
            label = f"{detection['class_name']} {detection['confidence']:.2f}"
            
            # Draw bounding box
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw label background
            cv2.rectangle(image, (x1, y1 - 20), (x1 + len(label) * 8, y1), (0, 255, 0), -1)
            
            # Draw label text
            cv2.putText(image, label, (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        cv2.imwrite(output_path, image)
        cv2.imshow('Combined Detection', image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        return output_path

# Usage
detector = CombinedDetector()
detections = detector.detect_combined('your_image.jpg')
print(f"Found {len(detections)} objects:")
for detection in detections:
    print(f"  - {detection['class_name']}: {detection['confidence']:.3f}")

detector.visualize_detections('your_image.jpg', detections)