
import uuid
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from database import Worker

class WorkerSessionManager:
    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory
        self.active_workers = {}
        # This would ideally be loaded from a persistent store or configuration
        # For now, we'll simulate a shift ID that might change daily or be configured.
        self.current_shift_id = "day_shift_" + date.today().strftime("%Y%m%d")

    def _get_db_session(self) -> Session:
        return self.db_session_factory()

    def start_worker_session(self, external_tracker_id: str) -> str:
        """
        Starts a new worker session or retrieves an existing one for the current day.
        Assigns a new anonymous worker_id if a new session is started or if the day has changed.
        """
        current_date = date.today()

        # Check if we have an active session for this external_tracker_id for today
        if external_tracker_id in self.active_workers:
            worker_info = self.active_workers[external_tracker_id]
            if worker_info["session_date"] == current_date:
                # Session is still valid for today
                return worker_info["worker_id"]
            else:
                # Day has changed, end old session and start a new one
                self.end_worker_session(external_tracker_id)

        # Create a new anonymous worker_id for the new session
        new_worker_uuid = str(uuid.uuid4())
        
        with self._get_db_session() as session:
            new_worker = Worker(
                worker_id=new_worker_uuid,
                session_date=current_date,
                shift_id=self.current_shift_id,
                created_at=datetime.now()
            )
            session.add(new_worker)
            session.commit()
            session.refresh(new_worker)

            self.active_workers[external_tracker_id] = {
                "worker_id": new_worker_uuid,
                "session_date": current_date,
                "db_id": new_worker.worker_id # Store the actual DB ID for reference
            }
            print(f"Started new session for external_tracker_id {external_tracker_id} with worker_id {new_worker_uuid}")
            return new_worker_uuid

    def end_worker_session(self, external_tracker_id: str):
        """
        Ends an active worker session and updates the 'ended_at' timestamp in the database.
        """
        if external_tracker_id in self.active_workers:
            worker_info = self.active_workers[external_tracker_id]
            db_worker_id = worker_info["db_id"]

            with self._get_db_session() as session:
                worker_to_update = session.query(Worker).filter_by(worker_id=db_worker_id).first()
                if worker_to_update:
                    worker_to_update.ended_at = datetime.now()
                    session.commit()
                    print(f"Ended session for worker_id {db_worker_id}")
                else:
                    print(f"Worker with db_id {db_worker_id} not found to end session.")
            del self.active_workers[external_tracker_id]
        else:
            print(f"No active session found for external_tracker_id {external_tracker_id} to end.")

    def get_worker_id(self, external_tracker_id: str) -> str | None:
        """
        Retrieves the current anonymous worker_id for a given external tracker ID.
        """
        worker_info = self.active_workers.get(external_tracker_id)
        if worker_info and worker_info["session_date"] == date.today():
            return worker_info["worker_id"]
        return None

    def reset_all_sessions_daily(self):
        """
        This method would be called periodically (e.g., once a day via a cron job)
        to ensure all sessions are reset and new worker_ids are generated for a new day.
        For simplicity, this example assumes `start_worker_session` handles daily reset implicitly.
        A more robust system would have a dedicated daily cleanup.
        """
        print("Daily session reset logic would be here. Handled implicitly by start_worker_session for now.")
        # In a real system, you might iterate through all active_workers and call end_worker_session
        # or clear self.active_workers and let new sessions be created.


# Example usage (for testing purposes, not part of the class itself)
if __name__ == '__main__':
    from database import init_db
    Session, engine = init_db("sqlite:///./test_liftbot.db")

    manager = WorkerSessionManager(Session)

    # Simulate tracking an object with external ID 'tracker_001'
    print("\n--- Day 1 --- ")
    worker_id_1 = manager.start_worker_session("tracker_001")
    print(f"Current worker_id for tracker_001: {manager.get_worker_id('tracker_001')}")

    # Simulate another event for the same tracker on the same day
    worker_id_1_again = manager.start_worker_session("tracker_001")
    print(f"Current worker_id for tracker_001 (again): {manager.get_worker_id('tracker_001')}")
    assert worker_id_1 == worker_id_1_again # Should be the same

    # Simulate a second worker
    worker_id_2 = manager.start_worker_session("tracker_002")
    print(f"Current worker_id for tracker_002: {manager.get_worker_id('tracker_002')}")

    # Simulate ending a session
    manager.end_worker_session("tracker_001")
    print(f"Worker_id for tracker_001 after ending: {manager.get_worker_id('tracker_001')}") # Should be None

    # --- Simulate a new day ---
    print("\n--- Simulating a new day ---")
    # To simulate a new day, we would typically restart the application or explicitly reset.
    # For this example, we'll manually change the current_shift_id and clear active_workers
    # In a real system, this would be handled by application restart or a scheduled task.
    manager.current_shift_id = "day_shift_" + (date.today() + timedelta(days=1)).strftime("%Y%m%d")
    manager.active_workers = {}

    worker_id_1_new_day = manager.start_worker_session("tracker_001")
    print(f"Current worker_id for tracker_001 on new day: {manager.get_worker_id('tracker_001')}")
    assert worker_id_1 != worker_id_1_new_day # Should be a new ID

    # Clean up test database
    import os
    os.remove("test_liftbot.db")
    print("\nCleaned up test_liftbot.db")

