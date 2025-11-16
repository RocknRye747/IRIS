
from datetime import datetime, date
from sqlalchemy.orm import Session
from database import Worker


class WorkerSessionManager:
    """Utility to mirror API worker session behavior for analyzer pipelines."""

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory
        self.active_workers = {}

    def _get_db_session(self) -> Session:
        return self.db_session_factory()

    def start_worker_session(self, external_tracker_id: str, site_id: str | None = None) -> str:
        """Create or reuse a worker session that matches the database schema."""

        current_date = date.today()
        cached_worker = self.active_workers.get(external_tracker_id)
        if cached_worker and cached_worker["session_start"].date() == current_date:
            return cached_worker["worker_id"]

        with self._get_db_session() as session:
            db_worker = (
                session.query(Worker)
                .filter(
                    Worker.external_tracker_id == external_tracker_id,
                    Worker.is_active.is_(True),
                )
                .first()
            )

            if db_worker and db_worker.session_start.date() == current_date:
                self.active_workers[external_tracker_id] = {
                    "worker_id": db_worker.worker_id,
                    "session_start": db_worker.session_start,
                }
                return db_worker.worker_id

            if db_worker:
                db_worker.is_active = False
                db_worker.session_end = datetime.utcnow()
                session.commit()

            new_worker = Worker(
                external_tracker_id=external_tracker_id,
                site_id=site_id,
                session_start=datetime.utcnow(),
                is_active=True,
            )
            session.add(new_worker)
            session.commit()
            session.refresh(new_worker)

            self.active_workers[external_tracker_id] = {
                "worker_id": new_worker.worker_id,
                "session_start": new_worker.session_start,
            }
            return new_worker.worker_id

    def end_worker_session(self, external_tracker_id: str):
        """Mark an in-memory and database session as ended."""

        worker_info = self.active_workers.pop(external_tracker_id, None)
        if not worker_info:
            return

        with self._get_db_session() as session:
            worker_to_update = session.query(Worker).filter_by(worker_id=worker_info["worker_id"]).first()
            if worker_to_update and worker_to_update.is_active:
                worker_to_update.is_active = False
                worker_to_update.session_end = datetime.utcnow()
                session.commit()

    def get_worker_id(self, external_tracker_id: str) -> str | None:
        worker_info = self.active_workers.get(external_tracker_id)
        if worker_info and worker_info["session_start"].date() == date.today():
            return worker_info["worker_id"]
        return None

    def reset_all_sessions_daily(self):
        """Clear cached sessions so a new worker_id is generated for the next day."""

        for tracker_id in list(self.active_workers.keys()):
            self.end_worker_session(tracker_id)


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

    # Clean up test database
    import os
    os.remove("test_liftbot.db")
    print("\nCleaned up test_liftbot.db")

