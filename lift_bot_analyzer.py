
import cv2
import mediapipe as mp
import numpy as np
from cjm_byte_track.byte_tracker import BYTETracker # Explicitly import BYTETracker from its module

from worker_tracker import WorkerSessionManager # Import our WorkerSessionManager
from database import init_db, LiftEvent # Import DB utilities
import json
from datetime import datetime

def calculate_angle(a, b, c):
    """
    Calculate the angle between three 3D points (landmarks).
    a, b, c are numpy arrays representing the (x, y, z) coordinates of the points.
    The angle is calculated at point b.
    """
    a = np.array(a) # First point
    b = np.array(b) # Mid point
    c = np.array(c) # End point

    # Create vectors BA and BC
    ba = a - b
    bc = c - b

    # Calculate dot product
    dot_product = np.dot(ba, bc)

    # Calculate magnitudes
    magnitude_ba = np.linalg.norm(ba)
    magnitude_bc = np.linalg.norm(bc)

    # Avoid division by zero
    if magnitude_ba == 0 or magnitude_bc == 0:
        return 0.0

    # Calculate cosine of the angle
    cosine_angle = dot_product / (magnitude_ba * magnitude_bc)

    # Ensure cosine_angle is within valid range [-1, 1] to prevent arccos errors
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)

    # Calculate angle in radians and convert to degrees
    angle_radians = np.arccos(cosine_angle)
    angle_degrees = np.degrees(angle_radians)

    return angle_degrees


def get_landmark_coordinates(landmarks, landmark_enum):
    """
    Extracts x, y, z coordinates for a given landmark from MediaPipe results.
    Returns None if the landmark is not detected or has low visibility.
    """
    if landmarks and landmarks.landmark[landmark_enum].visibility > 0.5:
        return [
            landmarks.landmark[landmark_enum].x,
            landmarks.landmark[landmark_enum].y,
            landmarks.landmark[landmark_enum].z
        ]
    return None

def analyze_pose(landmarks):
    """
    Analyzes the detected pose for ergonomic risks (back rounding, straight-leg lifts, twisting).
    Returns a dictionary with safe_lift (boolean), risk_score (0-100), and detailed angle_data.
    """
    risk_score = 0.0
    safe_lift = True
    angle_data = {}

    # Define landmark indices for clarity
    # Using MediaPipe Pose landmarks: https://google.github.io/mediapipe/solutions/pose.html
    LEFT_SHOULDER = mp.solutions.pose.PoseLandmark.LEFT_SHOULDER
    RIGHT_SHOULDER = mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER
    LEFT_HIP = mp.solutions.pose.PoseLandmark.LEFT_HIP
    RIGHT_HIP = mp.solutions.pose.PoseLandmark.RIGHT_HIP
    LEFT_KNEE = mp.solutions.pose.PoseLandmark.LEFT_KNEE
    RIGHT_KNEE = mp.solutions.pose.PoseLandmark.RIGHT_KNEE
    LEFT_ANKLE = mp.solutions.pose.PoseLandmark.LEFT_ANKLE
    NOSE = mp.solutions.pose.PoseLandmark.NOSE

    # Extract coordinates
    left_shoulder = get_landmark_coordinates(landmarks, LEFT_SHOULDER)
    right_shoulder = get_landmark_coordinates(landmarks, RIGHT_SHOULDER)
    left_hip = get_landmark_coordinates(landmarks, LEFT_HIP)
    right_hip = get_landmark_coordinates(landmarks, RIGHT_HIP)
    left_knee = get_landmark_coordinates(landmarks, LEFT_KNEE)
    right_knee = get_landmark_coordinates(landmarks, RIGHT_KNEE)
    left_ankle = get_landmark_coordinates(landmarks, LEFT_ANKLE)
    nose = get_landmark_coordinates(landmarks, NOSE)

    # --- Back Rounding (Spine Angle) --- 
    # Using mid-shoulder, mid-hip, and mid-knee to approximate torso bend relative to legs
    back_angle = None
    if all([left_shoulder, right_shoulder, left_hip, right_hip, left_knee, right_knee]):
        mid_shoulder = np.array([(left_shoulder[0] + right_shoulder[0]) / 2, (left_shoulder[1] + right_shoulder[1]) / 2, (left_shoulder[2] + right_shoulder[2]) / 2])
        mid_hip = np.array([(left_hip[0] + right_hip[0]) / 2, (left_hip[1] + right_hip[1]) / 2, (left_hip[2] + right_hip[2]) / 2])
        mid_knee = np.array([(left_knee[0] + right_knee[0]) / 2, (left_knee[1] + right_knee[1]) / 2, (left_knee[2] + right_knee[2]) / 2])

        # Angle between mid_shoulder - mid_hip - mid_knee (approximating torso bend relative to legs)
        back_angle = calculate_angle(mid_shoulder, mid_hip, mid_knee)
        angle_data['back_angle'] = round(back_angle, 2)

        # Risk calculation for back angle (more granular thresholds based on NIOSH/ergonomic guidelines)
        if back_angle is not None:
            if back_angle > 120: # Significant forward bend (e.g., stooping)
                back_risk = (back_angle - 120) * 2.0 # Higher penalty for extreme bend
                safe_lift = False
            elif back_angle > 90: # Moderate bend
                back_risk = (back_angle - 90) * 1.0
                safe_lift = False
            else:
                back_risk = 0
            risk_score += back_risk * 0.5 # Weight for back risk

    # --- Straight-Leg Lifts (Knee Angle) --- 
    knee_angle = None
    if all([left_hip, left_knee, left_ankle]):
        # Angle between hip-knee vector and knee-ankle vector
        knee_angle = calculate_angle(left_hip, left_knee, left_ankle)
        angle_data['left_knee_angle'] = round(knee_angle, 2)

        # Risk calculation for knee angle (emphasizing squat vs. stoop)
        if knee_angle is not None:
            if knee_angle > 160: # Legs too straight (stooping tendency)
                knee_risk = (knee_angle - 160) * 1.5 # Higher penalty for straight legs
                safe_lift = False
            elif knee_angle < 80: # Squatting too deep (can also be a risk if extreme, but less common for injury)
                knee_risk = (80 - knee_angle) * 0.5 # Moderate penalty
                safe_lift = False
            else:
                knee_risk = 0
            risk_score += knee_risk * 0.3 # Weight for knee risk

    # --- Twisting Under Load (Shoulder-Hip Alignment) --- 
    twist_angle = None
    if all([left_shoulder, right_shoulder, left_hip, right_hip]):
        # Project shoulder and hip vectors onto the XY plane to measure twist
        shoulder_vector = np.array(right_shoulder)[:2] - np.array(left_shoulder)[:2]
        hip_vector = np.array(right_hip)[:2] - np.array(left_hip)[:2]

        # Calculate the angle between these two 2D vectors
        dot_product = np.dot(shoulder_vector, hip_vector)
        magnitude_shoulder = np.linalg.norm(shoulder_vector)
        magnitude_hip = np.linalg.norm(hip_vector)

        if magnitude_shoulder > 0 and magnitude_hip > 0:
            cosine_angle = dot_product / (magnitude_shoulder * magnitude_hip)
            cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
            twist_angle = np.degrees(np.arccos(cosine_angle))
            angle_data['twist_angle'] = round(twist_angle, 2)

            # Risk for twisting: deviation from 0 or 180 degrees (parallel/anti-parallel)
            # A small angle (e.g., < 10 deg) or large angle (e.g., > 170 deg) means minimal twist
            # Angles around 90 degrees mean significant twist
            twist_deviation = min(abs(twist_angle), abs(180 - twist_angle))

            if twist_deviation > 20: # Significant twist
                twist_risk = (twist_deviation - 20) * 1.5
                safe_lift = False
            elif twist_deviation > 10: # Moderate twist
                twist_risk = (twist_deviation - 10) * 0.7
                safe_lift = False
            else:
                twist_risk = 0
            risk_score += twist_risk * 0.2 # Weight for twist risk

    # --- Head/Neck Posture (Approximation) ---
    # Check if head is excessively tilted forward or backward relative to shoulders
    neck_angle = None
    if all([nose, mid_shoulder]):
        # Approximate neck angle using nose, mid-shoulder, and a point above nose for vertical alignment
        # This is a simplified 2D projection for forward/backward tilt
        # More accurate would require 3D head orientation
        
        # Create a vertical reference point above the nose
        vertical_ref = np.array([nose[0], nose[1] - 0.1, nose[2]]) # 0.1 units above nose in Y-axis
        
        # Angle between vertical_ref - nose - mid_shoulder
        neck_angle = calculate_angle(vertical_ref, nose, mid_shoulder)
        angle_data['neck_angle'] = round(neck_angle, 2)

        if neck_angle is not None:
            if neck_angle > 100: # Head tilted too far forward
                neck_risk = (neck_angle - 100) * 0.8
                safe_lift = False
            elif neck_angle < 70: # Head tilted too far backward
                neck_risk = (70 - neck_angle) * 0.8
                safe_lift = False
            else:
                neck_risk = 0
            risk_score += neck_risk * 0.1 # Weight for neck risk

    # Cap risk score at 100
    risk_score = min(100, max(0, risk_score))

    # If any risk was detected, safe_lift is False
    if risk_score > 0:
        safe_lift = False
    else:
        safe_lift = True

    # --- Load Distance (Approximation) ---
    # Approximating horizontal distance from mid-hip to mid-wrist/hand
    load_distance = None
    if all([left_hip, right_hip, left_shoulder, right_shoulder, mp.solutions.pose.PoseLandmark.LEFT_WRIST, mp.solutions.pose.PoseLandmark.RIGHT_WRIST]):
        left_wrist = get_landmark_coordinates(landmarks, mp.solutions.pose.PoseLandmark.LEFT_WRIST)
        right_wrist = get_landmark_coordinates(landmarks, mp.solutions.pose.PoseLandmark.RIGHT_WRIST)

        if left_wrist and right_wrist:
            mid_hip = np.array([(left_hip[0] + right_hip[0]) / 2, (left_hip[1] + right_hip[1]) / 2, (left_hip[2] + right_hip[2]) / 2])
            mid_wrist = np.array([(left_wrist[0] + right_wrist[0]) / 2, (left_wrist[1] + right_wrist[1]) / 2, (left_wrist[2] + right_wrist[2]) / 2])

            # Calculate horizontal distance (ignoring Z for simplicity, or using Z if 3D is reliable)
            # This is a relative distance within the normalized coordinate system (0-1)
            load_distance = np.linalg.norm(mid_hip[:2] - mid_wrist[:2]) # Using XY plane distance
            angle_data["load_distance"] = round(load_distance, 4)

            # Risk calculation for load distance (thresholds are relative to normalized coordinates)
            if load_distance is not None:
                if load_distance > 0.3: # Object held far from body (relative to image size)
                    load_risk = (load_distance - 0.3) * 50 # Higher penalty
                    safe_lift = False
                elif load_distance > 0.15: # Moderate distance
                    load_risk = (load_distance - 0.15) * 20
                    safe_lift = False
                else:
                    load_risk = 0
                risk_score += load_risk * 0.15 # Weight for load distance

    # --- Asymmetry (Twisting) --- 
    # Re-evaluating twist with a more direct comparison of shoulder and hip alignment
    # This is already partially covered, but can be enhanced for explicit asymmetry.
    # The previous twist calculation is sufficient for now, but we can refine it if needed.
    # For now, the existing twist_angle calculation will serve as our asymmetry metric.

    # --- Lift Duration (Conceptual) ---
    # Lift duration requires tracking the start and end of a lift. This cannot be done within a single frame analysis.
    # It would require stateful tracking across multiple frames (e.g., detecting when hips/shoulders start moving down, then up).
    # For the current single-frame `analyze_pose` function, we will note this as a future enhancement.
    # Placeholder for future integration:
    # if lift_duration > X seconds: duration_risk = ...

    # Cap risk score at 100
    risk_score = min(100, max(0, risk_score))

    # If any risk was detected, safe_lift is False
    if risk_score > 0:
        safe_lift = False
    else:
        safe_lift = True

    return {"safe_lift": safe_lift, "risk_score": round(risk_score, 2), "angle_data": angle_data}


def main(video_path=None):
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils

    if video_path:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Error: Could not open video file {video_path}")
            return
    else:
        # Create a dummy video source for demonstration
        print("No video path provided. Using a dummy video source for demonstration.")
        dummy_frame_width = 640
        dummy_frame_height = 480
        dummy_fps = 10
        dummy_total_frames = 50 # Process 50 frames
        
        # Mock a cv2.VideoCapture object
        class DummyVideoCapture:
            def __init__(self, width, height, fps, total_frames):
                self._width = width
                self._height = height
                self._fps = fps
                self._total_frames = total_frames
                self._current_frame = 0

            def isOpened(self):
                return self._current_frame < self._total_frames

            def read(self):
                if self.isOpened():
                    # Create a black frame
                    frame = np.zeros((self._height, self._width, 3), dtype=np.uint8)
                    # Add some text to indicate it's a dummy frame
                    cv2.putText(frame, f"Dummy Frame {self._current_frame}/{self._total_frames}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
                    self._current_frame += 1
                    return True, frame
                return False, None

            def release(self):
                pass

        cap = DummyVideoCapture(dummy_frame_width, dummy_frame_height, dummy_fps, dummy_total_frames)

    # Initialize ByteTracker
    # ByteTracker expects detections in format [xmin, ymin, xmax, ymax, score, class_id]
    tracker = BYTETracker(track_thresh=0.5, track_buffer=30, match_thresh=0.8, frame_rate=30)



    # Initialize WorkerSessionManager
    Session, _ = init_db()
    worker_manager = WorkerSessionManager(Session)

    with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        frame_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            # Convert the BGR image to RGB.
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image.flags.writeable = False

            # Process the image and find poses.
            results = pose.process(image)

            # Draw the pose annotation on the image.
            image.flags.writeable = True
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

            detections = []
            # In a dummy video, there are no actual people, so we need to simulate a detection
            # For demonstration, let's create a fixed dummy detection if no real landmarks are found
            if not results.pose_landmarks:
                # Simulate a person in the center of the frame for tracking demonstration
                h, w, _ = image.shape
                dummy_xmin, dummy_ymin = w // 4, h // 4
                dummy_xmax, dummy_ymax = w * 3 // 4, h * 3 // 4
                detections.append([dummy_xmin, dummy_ymin, dummy_xmax, dummy_ymax, 0.99, 0])
            else:
                # Existing logic for real pose landmarks
                x_coords = [lmk.x for lmk in results.pose_landmarks.landmark if lmk.visibility > 0.5]
                y_coords = [lmk.y for lmk in results.pose_landmarks.landmark if lmk.visibility > 0.5]
                
                if x_coords and y_coords:
                    h, w, _ = image.shape
                    xmin = int(min(x_coords) * w)
                    ymin = int(min(y_coords) * h)
                    xmax = int(max(x_coords) * w)
                    ymax = int(max(y_coords) * h)
                    detections.append([xmin, ymin, xmax, ymax, 0.99, 0])

                mp_drawing.draw_landmarks(
                    image,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=2),
                    mp_drawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2)
                )

            # Update ByteTracker with current detections
            # BYTETracker.update expects img_info (original_h, original_w) and img_size (target_h, target_w)
            # For our dummy video, these are constant.
            img_info = (dummy_frame_height, dummy_frame_width)
            img_size = (dummy_frame_height, dummy_frame_width) # Assuming target size is same as original for simplicity
            # The cjm_byte_track library expects detections in a specific format.
            # If detections are provided as a NumPy array, it expects 5 columns (bbox + score).
            # If it has more, it tries to call .cpu().numpy() assuming it's a tensor.
            # We are providing [xmin, ymin, xmax, ymax, score, class_id], which is 6 columns.
            # To avoid the .cpu() error, we need to adjust the input format for BYTETracker.
            # Let's pass only the bounding box and score, making it 5 columns.
            detections_for_tracker = []
            if detections:
                for det in detections:
                    # Only take xmin, ymin, xmax, ymax, score
                    detections_for_tracker.append(det[:5])
            
            detections_np = np.array(detections_for_tracker) if detections_for_tracker else np.empty((0, 5)) # xmin, ymin, xmax, ymax, score
            tracked_objects = tracker.update(detections_np, img_info, img_size)



            # Process each tracked object
            db_session = Session()
            try:
                for i, track in enumerate(tracked_objects):
                    # Get bounding box and track_id
                    # STrack objects have attributes for bbox and track_id
                    x1, y1, x2, y2 = track.tlbr # Top-left, bottom-right bounding box
                    track_id = track.track_id
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

                    # Use track_id as external_tracker_id for WorkerSessionManager
                    external_tracker_id = str(track_id)
                    worker_id = worker_manager.start_worker_session(external_tracker_id)

                    # Perform ergonomic analysis for this tracked person
                    # For a dummy video, we don't have real pose landmarks, so simulate risk data
                    risk_data = {"safe_lift": True, "risk_score": 0.0} # Default if no real pose landmarks
                    if results.pose_landmarks:
                        risk_data = analyze_pose(results.pose_landmarks)
                    else:
                        # Simulate some risk data for the dummy tracked object
                        risk_data = {"safe_lift": False, "risk_score": float(np.random.randint(20, 80))} # Random risk for dummy

                    # Store lift event in DB
                    new_lift_event = LiftEvent(
                        worker_id=worker_id,
                        timestamp=datetime.now(),
                        risk_score=float(risk_data["risk_score"]),
                        safe_lift=risk_data["safe_lift"],
                        angle_data=json.dumps({"mock_angle_data": "placeholder"}) # Placeholder for actual angle data
                    )
                    db_session.add(new_lift_event)
                    db_session.commit()

                    # Display track_id, worker_id, and risk data on frame
                    color = (0, 255, 0) if risk_data["safe_lift"] else (0, 0, 255) # Green for safe, Red for unsafe
                    status_text = f"ID: {track_id} Worker: {worker_id[:4]}... Risk: {risk_data['risk_score']:.2f} - {'SAFE' if risk_data['safe_lift'] else 'UNSAFE'}"
                    cv2.putText(image, status_text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
                    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

                    print(f"Frame {frame_count}: Track ID {track_id}, Worker ID {worker_id[:8]}..., {status_text}")

            except Exception as e:
                db_session.rollback()
                print(f"Error during tracking/DB integration: {e}")
            finally:
                db_session.close()

            # In a headless environment, cv2.imshow is not supported.
            # We will skip displaying the image and instead rely on console output and database logging.
            # If a display is available, uncomment the following lines for visualization:
            # cv2.imshow("Lift Bot Analyzer", image)
            # if cv2.waitKey(10) & 0xFF == ord("q"):
            #     break

    cap.release()
    # cv2.destroyAllWindows() # Not needed in headless environment


if __name__ == '__main__':
    # For testing, you can place a video file in the sandbox and update this path.
    # Example: main("path/to/your/video.mp4")
    # If no video_path is provided, a dummy video source will be used.
    main()
