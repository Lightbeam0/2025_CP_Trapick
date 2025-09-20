# trapick/ml/train_yolo.py
from ultralytics import YOLO
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument('--data', default='data.yaml')   # path to data.yaml
parser.add_argument('--model', default='yolov8n.pt')            # pretrained starting weights (keep at repo root or change path)
parser.add_argument('--epochs', type=int, default=100)
parser.add_argument('--imgsz', type=int, default=640)
parser.add_argument('--project', default='runs')
parser.add_argument('--name', default='yolo_exp')
args = parser.parse_args()

os.makedirs(args.project, exist_ok=True)

model = YOLO(args.model)  # loads pretrained YOLOv8n weights
model.train(data=args.data,
            epochs=args.epochs,
            imgsz=args.imgsz,
            project=args.project,
            name=args.name)
