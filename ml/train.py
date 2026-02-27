import os
from ultralytics import YOLO

def train_collision_model():
    # 1. Load the Medium model (Best balance for 6GB VRAM)
    print("Loading yolov8m.pt...")
    model = YOLO('yolov8m.pt')  

    # 2. Define paths
    dataset_path = os.path.join(os.path.dirname(__file__), 'Collision-5', 'data.yaml')
    
    if not os.path.exists(dataset_path):
        print(f"Error: Dataset not found at {dataset_path}")
        return

    # 3. Train with GPU-Optimized Settings
    print("Starting training on GPU...")
    results = model.train(
        data=dataset_path,
        epochs=100,          # Full training cycle
        imgsz=640,           # Standard resolution
        batch=16,            # Fits well in 6GB VRAM for 'm' model. If OOM, drop to 8.
        name='custom_model', 
        exist_ok=True,
        device=0,            # Force usage of GPU 0 (your RTX 3050)
        patience=15,         # Stop early if no improvement after 15 epochs
        amp=True,            # Automatic Mixed Precision (Speeds up training on RTX cards)
        optimizer='SGD',     # Often yields better generalization than Adam for detection
        lr0=0.01,            # Standard initial learning rate
        cos_lr=True,         # Cosine annealing scheduler (helps converge better)
        close_mosaic=10,     # Disable mosaic augmentation for last 10 epochs (boosts accuracy)
        verbose=True         # Show detailed progress
    )

    print(f"Training complete! Best model: {results.save_dir / 'weights' / 'best.pt'}")

if __name__ == '__main__':
    train_collision_model()