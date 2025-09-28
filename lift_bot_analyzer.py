
import cv2
import mediapipe as mp
import numpy as np

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
    Analyzes the detected pose for ergonomic risks (back rounding, straight-leg lifts).
    Returns a dictionary with safe_lift (boolean) and risk_score (0-100).
    """
    risk_score = 0.0
    safe_lift = True

    # Define landmark indices for clarity
    # Using MediaPipe Pose landmarks: https://google.github.io/mediapipe/solutions/pose.html
    LEFT_SHOULDER = mp.solutions.pose.PoseLandmark.LEFT_SHOULDER
    RIGHT_SHOULDER = mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER
    LEFT_HIP = mp.solutions.pose.PoseLandmark.LEFT_HIP
    RIGHT_HIP = mp.solutions.pose.PoseLandmark.RIGHT_HIP
    LEFT_KNEE = mp.solutions.pose.PoseLandmark.LEFT_KNEE
    RIGHT_KNEE = mp.solutions.pose.PoseLandmark.RIGHT_KNEE
    LEFT_ANKLE = mp.solutions.pose.PoseLandmark.LEFT_ANKLE
    RIGHT_ANKLE = mp.solutions.pose.PoseLandmark.RIGHT_ANKLE

    # Extract coordinates
    left_shoulder = get_landmark_coordinates(landmarks, LEFT_SHOULDER)
    right_shoulder = get_landmark_coordinates(landmarks, RIGHT_SHOULDER)
    left_hip = get_landmark_coordinates(landmarks, LEFT_HIP)
    right_hip = get_landmark_coordinates(landmarks, RIGHT_HIP)
    left_knee = get_landmark_coordinates(landmarks, LEFT_KNEE)
    right_knee = get_landmark_coordinates(landmarks, RIGHT_KNEE)
    left_ankle = get_landmark_coordinates(landmarks, LEFT_ANKLE)
    right_ankle = get_landmark_coordinates(landmarks, RIGHT_ANKLE)

    # --- Back Rounding (Spine Angle) --- 
    # We'll use the left side for consistency, assuming symmetry
    if all([left_shoulder, right_shoulder, left_hip, right_hip, left_knee]):
        mid_shoulder = np.array([(left_shoulder[0] + right_shoulder[0]) / 2, (left_shoulder[1] + right_shoulder[1]) / 2, (left_shoulder[2] + right_shoulder[2]) / 2])
        mid_hip = np.array([(left_hip[0] + right_hip[0]) / 2, (left_hip[1] + right_hip[1]) / 2, (left_hip[2] + right_hip[2]) / 2])

        # Angle between shoulder-hip vector and hip-knee vector (approximating torso bend)
        # Points: mid_shoulder (A), mid_hip (B), left_knee (C)
        back_angle = calculate_angle(mid_shoulder, mid_hip, left_knee)

        # Risk calculation for back angle
        if back_angle > 60: # Significant forward bend
            back_risk = (back_angle - 60) * 1.5 # Higher penalty
            safe_lift = False
        elif back_angle > 30: # Moderate bend
            back_risk = (back_angle - 30) * 0.5
            safe_lift = False
        else:
            back_risk = 0
        
        # Weight for back risk
        risk_score += back_risk * 0.6

    # --- Straight-Leg Lifts (Knee Angle) --- 
    if all([left_hip, left_knee, left_ankle]):
        # Angle between hip-knee vector and knee-ankle vector
        # Points: left_hip (A), left_knee (B), left_ankle (C)
        knee_angle = calculate_angle(left_hip, left_knee, left_ankle)

        # Risk calculation for knee angle
        if knee_angle > 160: # Legs too straight
            knee_risk = (knee_angle - 160) * 1.0
            safe_lift = False
        elif knee_angle < 70: # Squatting too deep (also a risk)
            knee_risk = (70 - knee_angle) * 0.7
            safe_lift = False
        else:
            knee_risk = 0
        
        # Weight for knee risk
        risk_score += knee_risk * 0.25

    # --- Twisting Under Load (Approximation) --- 
    # This is harder to do accurately without a clear 'load' or 3D orientation
    # For now, we'll use a simple shoulder-hip alignment check.
    if all([left_shoulder, right_shoulder, left_hip, right_hip]):
        shoulder_vector = np.array(right_shoulder) - np.array(left_shoulder)
        hip_vector = np.array(right_hip) - np.array(left_hip)

        # Calculate angle between the two vectors projected onto the XY plane (ignoring Z for simplicity in 2D view)
        shoulder_vector_2d = shoulder_vector[:2]
        hip_vector_2d = hip_vector[:2]

        dot_product_2d = np.dot(shoulder_vector_2d, hip_vector_2d)
        magnitude_shoulder_2d = np.linalg.norm(shoulder_vector_2d)
        magnitude_hip_2d = np.linalg.norm(hip_vector_2d)

        if magnitude_shoulder_2d > 0 and magnitude_hip_2d > 0:
            cosine_angle_2d = dot_product_2d / (magnitude_shoulder_2d * magnitude_hip_2d)
            cosine_angle_2d = np.clip(cosine_angle_2d, -1.0, 1.0)
            twist_angle = np.degrees(np.arccos(cosine_angle_2d))
            
            # If the vectors are not aligned (i.e., angle is far from 0 or 180), there's a twist
            # We're looking for deviation from parallel (0 degrees) or anti-parallel (180 degrees)
            # A small angle (e.g., < 15 deg) or large angle (e.g., > 165 deg) means no twist
            # Angles around 90 degrees mean significant twist
            twist_deviation = min(abs(twist_angle), abs(180 - twist_angle))

            if twist_deviation > 15: # More than 15 degrees deviation from straight alignment
                twist_risk = (twist_deviation - 15) * 1.0
                safe_lift = False
            else:
                twist_risk = 0
            
            risk_score += twist_risk * 0.15

    # Cap risk score at 100
    risk_score = min(100, max(0, risk_score))

    # If any risk was detected, safe_lift is False
    if risk_score > 0:
        safe_lift = False
    else:
        safe_lift = True

    return {"safe_lift": safe_lift, "risk_score": round(risk_score, 2)}





def main(video_path):
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"Error: Could not open video file {video_path}")
        return

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

            risk_data = {"safe_lift": True, "risk_score": 0.0}
            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    image,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=2),
                    mp_drawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2)
                )
                risk_data = analyze_pose(results.pose_landmarks)

            # Display risk score and safe_lift status
            color = (0, 255, 0) if risk_data["safe_lift"] else (0, 0, 255) # Green for safe, Red for unsafe
            status_text = f"Risk: {risk_data['risk_score']:.2f} - {'SAFE' if risk_data['safe_lift'] else 'UNSAFE'}"
            cv2.putText(image, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2, cv2.LINE_AA)

            # Print to console
            print(f"Frame {frame_count}: {status_text}")

            # Display the image
            cv2.imshow('Lift Bot Analyzer', image)

            if cv2.waitKey(10) & 0xFF == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    # Placeholder for video path. User will need to provide a video file.
    # For testing, you can place a video file in the sandbox and update this path.
    # Example: main('path/to/your/video.mp4')
    print("Please provide a video file path to the main function in lift_bot_analyzer.py")
    print("Example: main('sample_lift.mp4')")
    # main('sample_lift.mp4') # Uncomment and provide your video path to run

