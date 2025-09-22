import os
from pathlib import Path

def verify_dataset_structure():
    """Verify that your YOLO dataset is properly structured"""
    # Use relative path from current directory (ml/)
    base_dir = Path("dataset")  # Changed from "trapick/ml/dataset"
    
    print("🔍 Verifying your dataset structure...\n")
    
    # Check if all required directories exist
    required_dirs = [
        "images/train",
        "images/val", 
        "labels/train",
        "labels/val"
    ]
    
    all_dirs_exist = True
    for dir_path in required_dirs:
        full_path = base_dir / dir_path
        if full_path.exists():
            print(f"✅ Found directory: {full_path}")
        else:
            print(f"❌ Missing directory: {full_path}")
            all_dirs_exist = False
    
    if not all_dirs_exist:
        print("\nPlease create the missing directories before proceeding.")
        return False
    
    print("\n📊 Checking dataset statistics:")
    
    # Count files in each directory
    for split in ["train", "val"]:
        image_dir = base_dir / "images" / split
        label_dir = base_dir / "labels" / split
        
        image_files = [f for f in os.listdir(image_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))]
        label_files = [f for f in os.listdir(label_dir) if f.endswith('.txt')]
        
        print(f"\n{split.upper()} SET:")
        print(f"  Images: {len(image_files)}")
        print(f"  Labels: {len(label_files)}")
        
        # Check for missing labels
        missing_labels = []
        for img_file in image_files:
            label_name = os.path.splitext(img_file)[0] + '.txt'
            if label_name not in label_files:
                missing_labels.append(img_file)
        
        if missing_labels:
            print(f"  ⚠️  {len(missing_labels)} images missing labels:")
            for img in missing_labels[:3]:  # Show first 3 missing labels
                print(f"    - {img}")
            if len(missing_labels) > 3:
                print(f"    ... and {len(missing_labels) - 3} more")
        else:
            print("  ✅ All images have corresponding labels")
    
    # Check data.yaml file - it should be in the current directory (ml/)
    yaml_path = Path("data.yaml")  # Changed from "ml/data.yaml"
    if yaml_path.exists():
        print(f"\n✅ Found data.yaml file")
        try:
            import yaml
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)
                print(f"  Classes: {data.get('names', 'Not specified')}")
                print(f"  Number of classes: {data.get('nc', 'Not specified')}")
                print(f"  Train path: {data.get('train', 'Not specified')}")
                print(f"  Val path: {data.get('val', 'Not specified')}")
        except Exception as e:
            print(f"  ⚠️  Could not parse data.yaml: {e}")
    else:
        print(f"\n❌ Missing data.yaml file")
        return False
    
    print("\n🎉 Dataset verification completed!")
    return True

# Run the verification
verify_dataset_structure()