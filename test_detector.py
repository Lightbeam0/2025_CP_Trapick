from ml.congestion_aware_detector import CongestionAwareDetector
detector = CongestionAwareDetector(roi=[100, 150, 500, 400], counting_line_y=300)
print(detector)