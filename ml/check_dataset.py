# check_dataset.py
import os
from pathlib import Path

def check_dataset_structure():
    base_path = Path('./dataset')
    
    print("Checking dataset structure...")
    print(f"Current working directory: {os.getcwd()}")
    
    # Check if dataset folder exists
    if not base_path.exists():
        print("❌ dataset folder does not exist!")
        return False
    
    # Check images
    train_images = base_path / 'images' / 'train'
    val_images = base_path / 'images' / 'val'
    
    print(f"Train images path: {train_images}")
    print(f"Val images path: {val_images}")
    
    if train_images.exists():
        image_files = list(train_images.glob('*.*'))
        print(f"Found {len(image_files)} training images")
        for img in image_files[:5]:  # Show first 5
            print(f"  - {img.name}")
    else:
        print("❌ Train images folder does not exist!")
    
    if val_images.exists():
        image_files = list(val_images.glob('*.*'))
        print(f"Found {len(image_files)} validation images")
    else:
        print("❌ Validation images folder does not exist!")
    
    # Check labels
    train_labels = base_path / 'labels' / 'train'
    val_labels = base_path / 'labels' / 'val'
    
    if train_labels.exists():
        label_files = list(train_labels.glob('*.txt'))
        print(f"Found {len(label_files)} training labels")
    else:
        print("❌ Train labels folder does not exist!")
    
    if val_labels.exists():
        label_files = list(val_labels.glob('*.txt'))
        print(f"Found {len(label_files)} validation labels")
    else:
        print("❌ Validation labels folder does not exist!")
    
    return True

if __name__ == "__main__":
    check_dataset_structure()