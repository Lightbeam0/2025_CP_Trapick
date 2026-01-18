import cv2
import sys
import os
import datetime

# Add the parent directory to Python path to import the module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.congestion_time_detector import CongestionTimeDetector

def test_image_detection(image_path):
    """
    Test congestion detection on a single image
    """
    print(f"🔍 Testing congestion detection on image: {image_path}")
    
    # Initialize the detector with adjusted parameters for single image
    detector = CongestionTimeDetector(
        model_path='yolov8l.pt',
        speed_threshold=5.0,
        stationary_threshold=10.0,
        min_vehicles_for_congestion=3,
        min_stable_frames=1,  # Lower for single image
        min_detection_confidence=0.3,  # Lower confidence threshold
        class_stability_threshold=0.5  # Lower threshold for single image
    )
    
    # Load the image
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"❌ Error: Cannot load image from {image_path}")
        return None
    
    h, w = frame.shape[:2]
    print(f"📐 Image dimensions: {w}x{h}")
    
    # Initialize detector for new image
    detector.reset_tracking_state()
    detector.setup_roi(w, h)
    
    # Process the frame (frame_number=0, fps=30)
    counts, detections = detector.process_frame(frame, frame_number=0, fps=30)
    
    # FIX: Clear counts and count properly
    counts = {}  # Reset counts
    seen_track_ids = set()  # Track unique vehicles
    
    for d in detections:
        d['is_stable'] = True
        vehicle_name = d['class_name']
        track_id = d.get('track_id', 0)
        
        # Only count each vehicle once
        if track_id not in seen_track_ids:
            counts[vehicle_name] = counts.get(vehicle_name, 0) + 1
            seen_track_ids.add(track_id)
    
    # Draw detections
    annotated_frame = detector.draw_detections(frame.copy(), detections, fps=30)
    
    # Display results
    print(f"\n📊 DETECTION RESULTS:")
    print(f"   Total detections: {len(detections)}")
    print(f"   Unique vehicles: {len(seen_track_ids)}")
    
    # Count unique vehicles
    total_counted = sum(counts.values()) if counts else 0
    print(f"   Vehicles counted: {total_counted}")
    
    if counts:
        print(f"\n   Vehicle Breakdown (Unique vehicles):")
        for vehicle_type, count in counts.items():
            print(f"   - {vehicle_type}: {count}")
    else:
        print(f"   No vehicles counted.")
    
    # Calculate congestion level - use unique vehicles
    congestion_level, vehicles_in_frame, congestion_score = detector.calculate_congestion_metrics(detections, fps=30)
    print(f"\n   🚦 Congestion Level: {congestion_level.upper()}")
    print(f"   📊 Vehicles in frame: {vehicles_in_frame}")
    print(f"   🎯 Congestion Score: {congestion_score}/100")
    
    # Save the annotated image
    output_dir = "media/processed_images"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a more descriptive filename
    original_filename = os.path.basename(image_path)
    filename_no_ext = os.path.splitext(original_filename)[0]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"congestion_{filename_no_ext}_{timestamp}.jpg"
    output_path = os.path.join(output_dir, output_filename)
    
    # Save the image
    success = cv2.imwrite(output_path, annotated_frame)
    
    if success:
        print(f"\n✅ SUCCESS: Annotated image saved to:")
        print(f"   📁 {output_path}")
        
        # Also save a smaller version if the image is too large
        if h > 1000 or w > 1000:
            # Resize for display
            scale = min(1000/w, 1000/h)
            new_w, new_h = int(w * scale), int(h * scale)
            resized = cv2.resize(annotated_frame, (new_w, new_h))
            
            resized_filename = f"congestion_{filename_no_ext}_{timestamp}_resized.jpg"
            resized_path = os.path.join(output_dir, resized_filename)
            cv2.imwrite(resized_path, resized)
            print(f"   📁 Resized version: {resized_path}")
    else:
        print(f"\n❌ ERROR: Failed to save image to {output_path}")
    
    # Generate a simple report
    print(f"\n📋 SUMMARY REPORT:")
    print(f"   Image: {os.path.basename(image_path)}")
    print(f"   Unique vehicles detected: {total_counted}")
    print(f"   Total detections: {len(detections)}")
    print(f"   Congestion level: {congestion_level}")
    print(f"   Congestion score: {congestion_score}/100")
    print(f"   Output saved: {output_path}")
    
    # Also create a text report file
    report_filename = f"report_{filename_no_ext}_{timestamp}.txt"
    report_path = os.path.join(output_dir, report_filename)
    
    with open(report_path, 'w') as f:
        f.write(f"Congestion Detection Report\n")
        f.write(f"="*50 + "\n")
        f.write(f"Image: {image_path}\n")
        f.write(f"Dimensions: {w}x{h}\n")
        f.write(f"Processing Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"\nResults:\n")
        f.write(f"- Total detections: {len(detections)}\n")
        f.write(f"- Unique vehicles: {total_counted}\n")
        f.write(f"- Congestion level: {congestion_level}\n")
        f.write(f"- Congestion score: {congestion_score}/100\n")
        f.write(f"\nVehicle Breakdown:\n")
        for vehicle_type, count in counts.items():
            f.write(f"- {vehicle_type}: {count}\n")
        f.write(f"\nOutput Files:\n")
        f.write(f"- Annotated image: {output_path}\n")
    
    print(f"📄 Text report saved to: {report_path}")
    
    # Print full output path
    print(f"\n📍 Full output path: {os.path.abspath(output_path)}")
    
    return {
        'image_path': image_path,
        'total_detections': len(detections),
        'unique_vehicles': total_counted,
        'vehicle_counts': dict(counts),
        'congestion_level': congestion_level,
        'congestion_score': congestion_score,
        'annotated_image_path': output_path,
        'report_path': report_path
    }

def display_image_safely(image_path, window_name="Congestion Detection"):
    """Safe way to display image without GUI issues"""
    try:
        # Try to display using matplotlib instead
        import matplotlib.pyplot as plt
        import matplotlib.image as mpimg
        
        img = mpimg.imread(image_path)
        plt.figure(figsize=(12, 8))
        plt.imshow(img)
        plt.title(window_name)
        plt.axis('off')
        plt.show()
        return True
    except ImportError:
        print("⚠️  matplotlib not installed. Skipping display.")
        return False
    except Exception as e:
        print(f"⚠️  Could not display image: {e}")
        return False

if __name__ == "__main__":
    # Default image path
    default_image_path = "C:/Users/naanu/Videos/Traffic San Jose Gusu/IMG_20251126_110334_262.jpg"
    
    # Check if command line argument is provided
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print(f"📁 Using command line argument: {image_path}")
    else:
        # Use the hardcoded default path
        image_path = default_image_path
        print(f"📁 Using default image path: {image_path}")
    
    # Check if file exists
    if not os.path.exists(image_path):
        print(f"❌ Error: Image file not found at: {image_path}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_dir = "media/processed_images"
    os.makedirs(output_dir, exist_ok=True)
    print(f"📁 Output directory: {os.path.abspath(output_dir)}")
    
    # Run the test
    print("\n" + "="*60)
    print("🚀 STARTING CONGESTION DETECTION")
    print("="*60)
    
    try:
        results = test_image_detection(image_path)
        
        if results:
            print(f"\n" + "="*60)
            print("✅ TEST COMPLETED SUCCESSFULLY!")
            print("="*60)
            print(f"\n📊 FINAL RESULTS:")
            print(f"   📸 Image: {os.path.basename(results['image_path'])}")
            print(f"   🔍 Total detections: {results['total_detections']}")
            print(f"   🚗 Unique vehicles: {results['unique_vehicles']}")
            print(f"   🚦 Congestion: {results['congestion_level'].upper()}")
            print(f"   🎯 Score: {results['congestion_score']}/100")
            print(f"   💾 Output: {results['annotated_image_path']}")
            
            # Show vehicle breakdown
            if results['vehicle_counts']:
                print(f"\n   📋 Vehicle Breakdown:")
                for vehicle_type, count in results['vehicle_counts'].items():
                    print(f"      • {vehicle_type}: {count}")
            
            # Ask if user wants to see the image
            response = input("\n👀 Do you want to view the annotated image? (y/n): ")
            if response.lower() == 'y':
                if display_image_safely(results['annotated_image_path'], 
                                      f"Congestion: {results['congestion_level'].upper()}"):
                    print("✅ Image displayed successfully!")
                else:
                    print("⚠️  Could not display image. Opening folder instead...")
                    
            # Open the folder containing the output
            print(f"\n📂 Opening output folder...")
            try:
                if sys.platform == "win32":
                    os.startfile(output_dir)
                elif sys.platform == "darwin":  # macOS
                    os.system(f'open "{output_dir}"')
                else:  # Linux
                    os.system(f'xdg-open "{output_dir}"')
                print(f"✅ Folder opened: {output_dir}")
            except:
                print(f"📁 You can find your files at: {os.path.abspath(output_dir)}")
                
    except Exception as e:
        print(f"\n❌ ERROR during processing: {e}")
        import traceback
        traceback.print_exc()