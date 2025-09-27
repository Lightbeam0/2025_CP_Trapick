# ml/config.py
import torch
import os

class Config:
    # GPU Configuration for RTX 3050
    DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {DEVICE}")
    
    # Model paths - adjust based on your actual file location
    MODEL_PATH = 'yolov8n.pt'  # This should be in your ml/ directory or project root
    
    # Vehicle classes from COCO dataset
    VEHICLE_CLASSES = {
        2: 'car',
        3: 'motorcycle', 
        5: 'bus',
        7: 'truck',
        1: 'bicycle'
    }
    
    # Detection confidence threshold
    CONFIDENCE_THRESHOLD = 0.4
    
    # Processing settings (adjust for performance)
    PROCESS_EVERY_N_FRAMES = 3
    
    # Create trackers directory if it doesn't exist
    TRACKER_DIR = 'ml/trackers'
    os.makedirs(TRACKER_DIR, exist_ok=True)