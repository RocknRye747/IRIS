
from database import init_db, Worker, LiftEvent, Report
from lift_bot_analyzer import analyze_pose # Assuming analyze_pose is available
from datetime import datetime, date
import uuid
import json
import mediapipe as mp # Import mediapipe to access PoseLandmark enums

# Placeholder for MediaPipe landmarks for demonstration purposes
# In a real scenario, this would come from the video processing pipeline
class MockLandmarks:
    def __init__(self, landmark_data_with_indices):
        # Initialize with 33 None values to match MediaPipe's 33 landmarks
        self.landmark = [None] * 33
        for landmark_enum_value, x, y, z, visibility in landmark_data_with_indices:
            mock_lm = type("Landmark", (object,), {"x": x, "y": y, "z": z, "visibility": visibility})
            self.landmark[landmark_enum_value] = mock_lm

def simulate_pose_data():
    """
    Generates mock pose landmark data for testing the analysis and database integration.
    This simulates a slightly bent back and slightly bent knees (moderate risk).
    """
    # Example landmarks (simplified for demonstration, real data would be more complex)
    # Format: (landmark_enum_value, x, y, z, visibility)
    # Using a subset of landmarks relevant for our analysis, mapping to MediaPipe's actual indices
    landmark_data_with_indices = [
        (mp.solutions.pose.PoseLandmark.LEFT_SHOULDER, 0.6, 0.4, 0.1, 0.9),
        (mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER, 0.4, 0.4, 0.1, 0.9),
        (mp.solutions.pose.PoseLandmark.LEFT_HIP, 0.6, 0.7, 0.0, 0.9),
        (mp.solutions.pose.PoseLandmark.RIGHT_HIP, 0.4, 0.7, 0.0, 0.9),
        (mp.solutions.pose.PoseLandmark.LEFT_KNEE, 0.6, 0.9, 0.0, 0.9),
        (mp.solutions.pose.PoseLandmark.RIGHT_KNEE, 0.4, 0.9, 0.0, 0.9),
        (mp.solutions.pose.PoseLandmark.LEFT_ANKLE, 0.6, 1.1, 0.0, 0.9),
        (mp.solutions.pose.PoseLandmark.RIGHT_ANKLE, 0.4, 1.1, 0.0, 0.9),
    ]
    return MockLandmarks(landmark_data_with_indices)

def main():
    Session, engine = init_db()
    session = Session()

    print("Database initialized and tables created (if not existing).")

    try:
        # 1. Simulate a new worker session
        shift_id = "day_B"
        new_worker = Worker(shift_id=shift_id)
        session.add(new_worker)
        session.commit()
        print(f"Created new worker session: {new_worker.worker_id}")

        # 2. Simulate a lift event and analyze it
        mock_landmarks = simulate_pose_data()
        analysis_result = analyze_pose(mock_landmarks)
        print(f"Simulated lift analysis result: {analysis_result}")

        # 3. Store the lift event in the database
        new_lift_event = LiftEvent(
            worker_id=new_worker.worker_id,
            timestamp=datetime.now(),
            risk_score=float(analysis_result["risk_score"]),
            safe_lift=analysis_result["safe_lift"],
            angle_data=json.dumps({"mock_angle_data": "placeholder"}) # In real app, store actual angle data
        )
        session.add(new_lift_event)
        session.commit()
        print(f"Stored lift event for worker {new_worker.worker_id} with risk score {new_lift_event.risk_score}")

        # 4. Simulate generating an aggregate report for the shift
        # In a real system, this would involve querying all lift events for the shift
        # For demonstration, we'll use a single event and mock aggregates
        total_lifts = 10
        safe_lifts = 8
        unsafe_lifts = 2
        avg_risk = 25.5

        new_report = Report(
            scope="manager",
            shift_id=shift_id,
            total_lifts=total_lifts,
            safe_lifts=safe_lifts,
            unsafe_lifts=unsafe_lifts,
            avg_risk=avg_risk,
            generated_at=datetime.now()
        )
        session.add(new_report)
        session.commit()
        print(f"Generated manager report for shift {shift_id} with avg risk {new_report.avg_risk}")

        # Verify data by querying
        retrieved_worker = session.query(Worker).filter_by(worker_id=new_worker.worker_id).first()
        print(f"Retrieved worker: {retrieved_worker}")
        print(f"Worker has {len(retrieved_worker.lift_events)} lift events.")

        retrieved_report = session.query(Report).filter_by(shift_id=shift_id, scope="manager").first()
        print(f"Retrieved report: {retrieved_report}")

    except Exception as e:
        session.rollback()
        print(f"An error occurred: {e}")
    finally:
        session.close()

if __name__ == '__main__':
    main()

