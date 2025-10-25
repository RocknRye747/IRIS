from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
import json
import uuid

from database import Site, Worker, LiftEvent, Report

class DataAccessLayer:
    def __init__(self, db_session: Session):
        self.db = db_session

    # --- Site Operations ---
    def create_site(self, site_name: str, location: Optional[str] = None) -> Site:
        site = Site(site_name=site_name, location=location)
        self.db.add(site)
        self.db.commit()
        self.db.refresh(site)
        return site

    def get_site_by_name(self, site_name: str) -> Optional[Site]:
        return self.db.query(Site).filter(Site.site_name == site_name).first()

    def get_site_by_id(self, site_id: str) -> Optional[Site]:
        return self.db.query(Site).filter(Site.site_id == site_id).first()

    def get_all_sites(self) -> List[Site]:
        return self.db.query(Site).all()

    # --- Worker Operations ---
    def create_worker_session(self, external_tracker_id: str, site_id: Optional[str] = None) -> Worker:

        existing_active_worker = self.db.query(Worker).filter(
            Worker.external_tracker_id == external_tracker_id,
            Worker.is_active == True
        ).first()
        if existing_active_worker:
            return existing_active_worker

        # If no active worker, check for any existing worker (active or inactive) with the same external_tracker_id
        # If found, reactivate it and create a new session for it.
        existing_worker = self.db.query(Worker).filter(
            Worker.external_tracker_id == external_tracker_id
        ).first()

        if existing_worker:
            # Reactivate the existing worker for a new session
            existing_worker.session_start = datetime.utcnow()
            existing_worker.session_end = None
            existing_worker.is_active = True
            existing_worker.site_id = site_id # Update site_id if it changed
            self.db.commit()
            self.db.refresh(existing_worker)
            return existing_worker

        # If no worker (active or inactive) exists, create a brand new one
        worker = Worker(
            external_tracker_id=external_tracker_id,
            site_id=site_id,
            session_start=datetime.utcnow(),
            is_active=True
        )
        self.db.add(worker)
        self.db.commit()
        self.db.refresh(worker)
        return worker

    def get_worker_by_id(self, worker_id: str) -> Optional[Worker]:
        return self.db.query(Worker).filter(Worker.worker_id == worker_id).first()

    def get_active_worker_by_external_id(self, external_tracker_id: str) -> Optional[Worker]:
        return self.db.query(Worker).filter(
            Worker.external_tracker_id == external_tracker_id,
            Worker.is_active == True
        ).first()

    def end_worker_session(self, worker_id: str) -> Optional[Worker]:
        worker = self.get_worker_by_id(worker_id)
        if worker:
            worker.is_active = False
            worker.session_end = datetime.utcnow()
            self.db.commit()
            self.db.refresh(worker)
        return worker

    # --- LiftEvent Operations ---
    def create_lift_event(self, worker_id: str, risk_score: float, safe_lift: bool, angle_data: Optional[Dict[str, Any]] = None, timestamp: Optional[datetime] = None) -> LiftEvent:
        lift_event = LiftEvent(
            worker_id=worker_id,
            timestamp=timestamp if timestamp else datetime.utcnow(),
            risk_score=risk_score,
            safe_lift=safe_lift,
            angle_data=angle_data # SQLAlchemy handles JSON serialization for Dict[str, Any]
        )
        self.db.add(lift_event)
        self.db.commit()
        self.db.refresh(lift_event)
        return lift_event

    def get_lift_events_by_worker_and_date(self, worker_id: str, target_date: date) -> List[LiftEvent]:
        return self.db.query(LiftEvent).filter(
            LiftEvent.worker_id == worker_id,
            func.date(LiftEvent.timestamp) == target_date
        ).all()

    def get_lift_events_in_period(self, start_date: date, end_date: date, site_id: Optional[str] = None) -> List[LiftEvent]:
        query = self.db.query(LiftEvent).filter(
            func.date(LiftEvent.timestamp) >= start_date,
            func.date(LiftEvent.timestamp) <= end_date
        )
        if site_id:
            query = query.join(Worker).filter(Worker.site_id == site_id)
        return query.all()

    # --- Report Operations ---
    def create_report(self, scope: str, period_start: date, period_end: date, total_lifts: int, safe_lifts: int, unsafe_lifts: int, avg_risk: float, worker_id: Optional[str] = None, site_id: Optional[str] = None, trend_data: Optional[Dict[str, Any]] = None) -> Report:
        report = Report(
            scope=scope,
            worker_id=worker_id,
            site_id=site_id,
            period_start=period_start,
            period_end=period_end,
            total_lifts=total_lifts,
            safe_lifts=safe_lifts,
            unsafe_lifts=unsafe_lifts,
            avg_risk=avg_risk,
            trend_data=json.dumps(trend_data) if trend_data else None
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def get_reports(self, scope: Optional[str] = None, worker_id: Optional[str] = None, site_id: Optional[str] = None, period_start: Optional[date] = None, period_end: Optional[date] = None) -> List[Report]:
        query = self.db.query(Report)
        if scope: query = query.filter(Report.scope == scope)
        if worker_id: query = query.filter(Report.worker_id == worker_id)
        if site_id: query = query.filter(Report.site_id == site_id)
        if period_start: query = query.filter(Report.period_start >= period_start)
        if period_end: query = query.filter(Report.period_end <= period_end)
        return query.all()

    # --- Data Deletion ---
    def delete_worker_data(self, worker_id: str) -> Dict[str, int]:
        lift_events_deleted = self.db.query(LiftEvent).filter(LiftEvent.worker_id == worker_id).delete(synchronize_session=False)
        worker_deleted = self.db.query(Worker).filter(Worker.worker_id == worker_id).delete(synchronize_session=False)
        self.db.commit()
        return {"lift_events_deleted": lift_events_deleted, "worker_records_deleted": worker_deleted}

