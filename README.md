# Trapick-Camera-based-Traffic-Data-Analysis-System-for-Smart-Traffic-Solution
Capstone Project 2025-2026

The project codes are all located in the master branch

##  Overview

Trapick is an intelligent traffic monitoring system that:
- Automatically detects and classifies vehicles in pre-recorded videos
- Tracks individual vehicles across frames
- Generates comprehensive traffic analytics
- Predicts peak congestion times

Built with **Django**, **React**, **OpenCV**, and **YOLOv8** for accurate real-world traffic analysis.

##  Key Features

- **Vehicle Detection**:
  - Cars, trucks, buses, motorcycles classification
  - YOLOv8 object detection model
  - Configurable model size (nano to extra-large)

- **Traffic Analytics**:
  - Vehicles per hour/day statistics
  - Speed distribution analysis
  - Congestion heatmaps
  - Historical trend visualization

- **Data Management**:
  - Video processing pipeline
  - Database storage of detection results
  - Exportable reports (CSV, JSON)

## Technical Stack

| Component          | Technology |
|--------------------|------------|
| Backend Framework  | Django 4.2 |
| Frontend           | React 18   |
| Computer Vision    | OpenCV, YOLOv8 |
| Database           | PostgreSQL (SQLite for dev) |
| Task Queue         | Celery + Redis |
| Visualization      | Chart.js |
