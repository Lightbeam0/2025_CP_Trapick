import torch
import os
from pathlib import Path

class Config:
    # GPU Configuration for RTX 3050
    DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {DEVICE}")
    
    # Model paths - UPDATED TO USE collision4_model
    COLLISION4_MODEL_PATH = 'runs/detect/collision4_model/weights/best.pt'
    
    # Vehicle classes from COLLISION4 model (excluding VehicleCrash=0 and person=4)
    VEHICLE_CLASSES = {
        1: 'car',
        2: 'jeep', 
        3: 'motorcycle',
        5: 'tricycle',
        6: 'truck'
    }
    
    # All classes in model (for reference)
    ALL_MODEL_CLASSES = {
        0: 'VehicleCrash',  # EXCLUDED from tracking
        1: 'car',
        2: 'jeep',
        3: 'motorcycle',
        4: 'person',        # EXCLUDED from tracking
        5: 'tricycle',
        6: 'truck'
    }
    
    # Detection confidence threshold (based on model performance)
    CONFIDENCE_THRESHOLD = 0.4  # Can adjust based on your needs
    
    # IoU threshold from training
    IOU_THRESHOLD = 0.7
    
    # Processing settings (adjust for RTX 3050 performance)
    PROCESS_EVERY_N_FRAMES = 3
    
    # Counting zone settings
    ZONE_HEIGHT_RATIO = (0.60, 0.85)
    ZONE_WIDTH_RATIO = (0.05, 0.95)
    
    # Create trackers directory if it doesn't exist
    TRACKER_DIR = 'ml/trackers'
    os.makedirs(TRACKER_DIR, exist_ok=True)