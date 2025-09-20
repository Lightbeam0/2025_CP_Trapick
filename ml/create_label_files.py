# create_label_files.py
import os
from pathlib import Path

def create_label_files():
    base = Path('./dataset')
    
    # For each image in train, create label file if it doesn't exist
    train_images = base / 'images' / 'train'
    train_labels = base / 'labels' / 'train'
    
    for image_file in train_images.iterdir():
        if image_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']:
            label_file = train_labels / f"{image_file.stem}.txt"
            
            if not label_file.exists():
                # Create label file with your actual annotations
                # Format: class_id center_x center_y width_height
                with open(label_file, 'w') as f:
                    # You need to replace this with your actual bounding box coordinates!
                    # Example: class 0 (Jeepney) at center of image
                    f.write("0 0.5 0.5 0.3 0.4\n")
                print(f"Created label: {label_file.name}")
    
    # Do the same for validation images
    val_images = base / 'images' / 'val'
    val_labels = base / 'labels' / 'val'
    
    for image_file in val_images.iterdir():
        if image_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']:
            label_file = val_labels / f"{image_file.stem}.txt"
            
            if not label_file.exists():
                with open(label_file, 'w') as f:
                    f.write("0 0.5 0.5 0.3 0.4\n")
                print(f"Created label: {label_file.name}")

if __name__ == "__main__":
    create_label_files()