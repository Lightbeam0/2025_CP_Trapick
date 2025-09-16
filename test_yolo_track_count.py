import cv2
import csv
import numpy as np
from collections import Counter, defaultdict
from ultralytics import YOLO
import math

# ---------- CONFIG ----------
MODEL_NAME = "yolo11n.pt"   # try "yolo11s.pt" or "yolov8n.pt" if you don't have yolo11
VIDEO_PATH = r"C:\Users\naanu\Downloads\D11_20250903090256.mp4"
OUTPUT_VIDEO = "output_tracked.mp4"
OUTPUT_CSV = "line_cross_counts.csv"

CONF_THRESH = 0.4     # ignore detections with conf < this
IOU_MATCH_THRESH = 0.3
MAX_MISSED_FRAMES = 30   # how long a track can be unseen before removal (frames)
LINE_Y = None   # set later to frame_middle if None
# ----------------------------

model = YOLO(MODEL_NAME)

cap = cv2.VideoCapture(VIDEO_PATH)
fps = cap.get(cv2.CAP_PROP_FPS) or 25
fps = int(fps)
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

if LINE_Y is None:
    LINE_Y = int(h * 0.55)  # adjust if you want the counting line lower/higher

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, fps, (w, h))

# simple IoU function
def iou(boxA, boxB):
    # boxes are [x1,y1,x2,y2]
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    inter = interW * interH
    areaA = max(0, (boxA[2]-boxA[0]) * (boxA[3]-boxA[1]))
    areaB = max(0, (boxB[2]-boxB[0]) * (boxB[3]-boxB[1]))
    union = areaA + areaB - inter + 1e-6
    return inter / union

# Track structure:
# tracks[id] = {
#   'bbox': [x1,y1,x2,y2],
#   'last_seen': frame_idx,
#   'class_votes': Counter(),
#   'centroids': [(cx,cy), ...],
#   'counted': False
# }
tracks = {}
next_track_id = 0

frame_idx = 0

# Prepare CSV writer: one row per second with counts for classes we care about
classes_of_interest = ['car', 'motorcycle', 'truck', 'bus', 'others']
csv_f = open(OUTPUT_CSV, "w", newline="")
csv_writer = csv.writer(csv_f)
csv_writer.writerow(["second"] + classes_of_interest)

# holder for line-cross events per second
per_second_counts = defaultdict(Counter)

print("Processing... press Ctrl-C to stop (partial results may be left).")

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        results = model(frame, conf=CONF_THRESH, iou=0.5)  # adjust iou if needed
        res = results[0]

        det_bboxes = []
        for box in res.boxes:
            conf = float(box.conf[0]) if hasattr(box, "conf") else float(box.conf)
            if conf < CONF_THRESH:
                continue
            # get xyxy
            # box.xyxy is tensor-like: get as flat list
            xy = box.xyxy[0].cpu().numpy() if hasattr(box.xyxy[0], "cpu") else box.xyxy[0].numpy()
            x1, y1, x2, y2 = map(int, xy.tolist())
            cls_id = int(box.cls[0]) if hasattr(box.cls, "__len__") else int(box.cls)
            cls_name = model.names[cls_id].lower()
            det_bboxes.append({'xy':[x1,y1,x2,y2], 'cls': cls_name, 'conf': conf})

        # -- Association: naive greedy IoU matching detections -> existing tracks
        assigned_tracks = set()
        for det in det_bboxes:
            best_track = None
            best_iou = 0.0
            for tid, t in tracks.items():
                if t['last_seen'] < frame_idx - MAX_MISSED_FRAMES:
                    continue
                i = iou(det['xy'], t['bbox'])
                if i > best_iou and i >= IOU_MATCH_THRESH:
                    best_iou = i
                    best_track = tid
            if best_track is not None:
                # update track
                t = tracks[best_track]
                t['bbox'] = det['xy']
                t['last_seen'] = frame_idx
                t['class_votes'][det['cls']] += 1
                cx = int((det['xy'][0] + det['xy'][2]) / 2)
                cy = int((det['xy'][1] + det['xy'][3]) / 2)
                t['centroids'].append((cx, cy))
                assigned_tracks.add(best_track)
            else:
                # create new track
                nonlocal_id = next_track_id
                tracks[nonlocal_id] = {
                    'bbox': det['xy'],
                    'last_seen': frame_idx,
                    'class_votes': Counter([det['cls']]),
                    'centroids': [ (int((det['xy'][0]+det['xy'][2])/2), int((det['xy'][1]+det['xy'][3])/2)) ],
                    'counted': False
                }
                next_track_id += 1

        # mark tracks as missed if not updated
        for tid in list(tracks.keys()):
            if tid not in assigned_tracks:
                # if not updated this frame, last_seen unchanged
                # remove stale tracks
                if tracks[tid]['last_seen'] < frame_idx - MAX_MISSED_FRAMES:
                    del tracks[tid]

        # Check for line-crossing for tracks updated this frame
        for tid, t in tracks.items():
            if len(t['centroids']) < 2 or t['counted']:
                continue
            (px, py), (cx, cy) = t['centroids'][-2], t['centroids'][-1]
            # we assume downward crossing: previous above line, current below line -> crossing
            # adjust depending on camera orientation
            if (py < LINE_Y <= cy) or (py > LINE_Y >= cy):
                # track crosses line
                majority_class = t['class_votes'].most_common(1)[0][0]
                crossing_second = math.ceil(frame_idx / fps)
                # normalize classes: if not in interest list -> others
                cls_for_count = majority_class if majority_class in classes_of_interest else 'others'
                per_second_counts[crossing_second][cls_for_count] += 1
                t['counted'] = True  # avoid double counting same track
                # optionally delete track after counted:
                # del tracks[tid]

        # Annotate frame for video output
        # draw counting line
        cv2.line(frame, (0, LINE_Y), (w, LINE_Y), (0,255,255), 2)
        # draw tracks
        for tid, t in tracks.items():
            x1,y1,x2,y2 = t['bbox']
            maj = t['class_votes'].most_common(1)[0][0]
            label = f"ID{tid}:{maj}"
            cv2.rectangle(frame, (x1,y1), (x2,y2), (0,200,0), 2)
            cv2.putText(frame, label, (x1, max(10,y1-6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

        out.write(frame)

        # Every second, flush per-second counts to CSV
        if frame_idx % fps == 0:
            second_no = frame_idx // fps
            row = [second_no]
            for cls in classes_of_interest:
                row.append(per_second_counts[second_no].get(cls, 0))
            csv_writer.writerow(row)

except KeyboardInterrupt:
    print("Interrupted by user.")
finally:
    cap.release()
    out.release()
    # flush remaining seconds if any
    last_sec = math.ceil(frame_idx / fps)
    for s in range(1, last_sec + 1):
        if s in per_second_counts:
            row = [s] + [per_second_counts[s].get(c, 0) for c in classes_of_interest]
            csv_writer.writerow(row)
    csv_f.close()

print("Done. Output video:", OUTPUT_VIDEO, "CSV:", OUTPUT_CSV)



