# trapick/ml/train_yolo_optimized.py
from ultralytics import YOLO
import argparse
import os
import datetime
import yaml
import torch

def check_hardware():
    """Check available hardware and recommend settings"""
    print("🖥️  Hardware Detection:")
    print(f"   CPU: Intel i5 13th Gen")
    print(f"   GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None detected'}")
    print(f"   GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB" if torch.cuda.is_available() else "   No GPU detected")
    print(f"   CUDA Available: {torch.cuda.is_available()}")
    print(f"   RAM: 16 GB")

def recommend_settings():
    """Recommend optimal settings based on hardware"""
    batch_size = 12  # Good starting point for RTX 3050
    workers = 6      # i5 can handle multiple workers
    
    print("\n🎯 Recommended Settings for Your Hardware:")
    print(f"   Batch Size: {batch_size} (adjust based on GPU memory)")
    print(f"   Workers: {workers} (for data loading)")
    print(f"   Image Size: 640 (optimal for detection)")
    print(f"   Use GPU: Yes (much faster than CPU)")
    
    return batch_size, workers

def load_config():
    """Load and display training configuration"""
    with open('data.yaml', 'r') as f:
        data_config = yaml.safe_load(f)
    
    print("\n📋 Training Configuration:")
    print(f"   Model: yolov8n.pt")
    print(f"   Epochs: 100")
    print(f"   Classes: {data_config['names']}")
    print(f"   Training images: {count_files('dataset/images/train')}")
    print(f"   Validation images: {count_files('dataset/images/val')}")

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
    parser.add_argument('--batch', type=int, default=12, help='batch size (adjust based on GPU memory)')
    parser.add_argument('--workers', type=int, default=6, help='number of data loading workers')
    parser.add_argument('--project', default='runs/detect', help='project directory')
    parser.add_argument('--name', default='jeepney_detection', help='experiment name')
    parser.add_argument('--device', default='0', help='device to use (0 for GPU, cpu for CPU)')
    
    args = parser.parse_args()

    # Display hardware info and recommendations
    check_hardware()
    recommended_batch, recommended_workers = recommend_settings()
    
    # Use recommended values if not specified
    if args.batch == 12:  # Default value
        args.batch = recommended_batch
    if args.workers == 6:  # Default value
        args.workers = recommended_workers
    
    load_config()
    print(f"   Batch Size: {args.batch}")
    print(f"   Workers: {args.workers}")
    print(f"   Start time: {datetime.datetime.now()}")

    # Load model
    print("\n🔄 Loading model...")
    model = YOLO(args.model)

    # Train the model
    print("🚀 Starting training...")
    try:
        results = model.train(
            data=args.data,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            workers=args.workers,
            project=args.project,
            name=args.name,
            device=args.device,
            patience=25,           # Early stopping patience
            optimizer='AdamW',     # Optimizer - good for your hardware
            lr0=0.001,            # Initial learning rate
            lrf=0.01,             # Final learning rate
            momentum=0.937,       # Momentum
            weight_decay=0.0005,  # Weight decay
            warmup_epochs=3.0,    # Warmup epochs
            augment=True,         # Apply data augmentation
            save=True,            # Save checkpoints
            val=True,             # Validate during training
            exist_ok=True,        # Overwrite existing experiment
            verbose=True,         # Verbose output
            # Additional augmentation settings that work well with your GPU
            hsv_h=0.015,          # Image HSV-Hue augmentation
            hsv_s=0.7,            # Image HSV-Saturation augmentation
            hsv_v=0.4,            # Image HSV-Value augmentation
            degrees=10.0,         # Image rotation
            translate=0.1,        # Image translation
            scale=0.5,            # Image scale
            flipud=0.0,           # Image flip up-down
            fliplr=0.5,           # Image flip left-right
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
            
    except RuntimeError as e:
        if "CUDA out of memory" in str(e):
            print("\n❌ CUDA Out of Memory Error!")
            print("💡 Try reducing batch size: --batch 8")
            print("💡 Or reduce image size: --imgsz 512")
        else:
            raise e

if __name__ == "__main__":
    main()