# trapick/ml/train_yolo.py
from ultralytics import YOLO
import argparse
import os
import datetime
import yaml

def load_config():
    """Load and display training configuration"""
    with open('data.yaml', 'r') as f:
        data_config = yaml.safe_load(f)
    
    print("📋 Training Configuration:")
    print(f"   Model: yolov8n.pt")
    print(f"   Epochs: 100")
    print(f"   Image size: 640")
    print(f"   Classes: {data_config['names']}")
    print(f"   Training images: {count_files('dataset/images/train')}")
    print(f"   Validation images: {count_files('dataset/images/val')}")
    print(f"   Start time: {datetime.datetime.now()}")

def count_files(directory):
    """Count image files in directory"""
    if not os.path.exists(directory):
        return 0
    return len([f for f in os.listdir(directory) 
               if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))])

def main():
    parser = argparse.ArgumentParser(description='Train YOLOv8 model for Jeepney detection')
    parser.add_argument('--data', default='data.yaml', help='path to data.yaml')
    parser.add_argument('--model', default='yolov8n.pt', help='pretrained model weights')
    parser.add_argument('--epochs', type=int, default=100, help='number of training epochs')
    parser.add_argument('--imgsz', type=int, default=640, help='image size for training')
    parser.add_argument('--batch', type=int, default=16, help='batch size')
    parser.add_argument('--project', default='runs/detect', help='project directory')
    parser.add_argument('--name', default='jeepney_detection', help='experiment name')
    parser.add_argument('--device', default='0', help='device to use (e.g., 0 for GPU, cpu for CPU)')
    
    args = parser.parse_args()

    # Display configuration
    load_config()

    # Load model
    print("🔄 Loading model...")
    model = YOLO(args.model)

    # Train the model
    print("🚀 Starting training...")
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project=args.project,
        name=args.name,
        device=args.device,
        patience=30,           # Early stopping patience
        optimizer='Adam',      # Optimizer
        lr0=0.001,            # Initial learning rate
        augment=True,          # Apply data augmentation
        save=True,             # Save checkpoints
        val=True,              # Validate during training
        workers=8,             # Number of worker threads
        exist_ok=True,         # Overwrite existing experiment
        verbose=True,          # Verbose output
    )

    print("✅ Training completed!")
    print(f"📅 End time: {datetime.datetime.now()}")
    
    # Export model to ONNX format
    print("📦 Exporting model to ONNX format...")
    model.export(format='onnx')
    
    # Save the final model
    model.save('best_jeepney_model.pt')
    print("💾 Model saved as 'best_jeepney_model.pt'")
    
    # Print final metrics
    if hasattr(results, 'box'):
        print("\n📈 Final Metrics:")
        print(f"   mAP50-95: {results.box.map:.4f}")
        print(f"   mAP50: {results.box.map50:.4f}")
        print(f"   Precision: {results.box.mp:.4f}")
        print(f"   Recall: {results.box.mr:.4f}")

if __name__ == "__main__":
    main()
