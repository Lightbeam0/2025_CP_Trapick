# final_check.py
from pathlib import Path

def final_check():
    base = Path('./dataset')
    
    print("=== FINAL DATASET CHECK ===")
    print(f"Training images: {len(list((base/'images'/'train').glob('*.jpg')))}")
    print(f"Validation images: {len(list((base/'images'/'val').glob('*.jpg')))}")
    print(f"Training labels: {len(list((base/'labels'/'train').glob('*.txt')))}")
    print(f"Validation labels: {len(list((base/'labels'/'val').glob('*.txt')))}")
    
    # Check if numbers match
    train_images = len(list((base/'images'/'train').glob('*.jpg')))
    train_labels = len(list((base/'labels'/'train').glob('*.txt')))
    val_images = len(list((base/'images'/'val').glob('*.jpg')))
    val_labels = len(list((base/'labels'/'val').glob('*.txt')))
    
    if train_images == train_labels and val_images == val_labels:
        print("✅ All images have corresponding labels!")
    else:
        print("❌ Mismatch between images and labels!")
    
    # Check classes.txt
    try:
        with open('classes.txt', 'r') as f:
            classes = [line.strip() for line in f if line.strip()]
        print(f"Classes: {classes}")
    except:
        print("❌ classes.txt not found or empty!")

if __name__ == "__main__":
    final_check()