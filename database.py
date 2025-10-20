from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.types import JSON # Use generic JSON type for broader compatibility
from datetime import datetime, date
import uuid

Base = declarative_base()

class Site(Base):
    __tablename__ = 'sites'

    site_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    site_name = Column(String, unique=True, nullable=False) # Added unique constraint
    location = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    workers = relationship('Worker', back_populates='site')
    reports = relationship('Report', back_populates='site_obj') # Renamed to avoid conflict with site_id column

    def __repr__(self):
        return f"<Site(site_id='{self.site_id}', site_name='{self.site_name}')>"

class Worker(Base):
    __tablename__ = 'workers'

    worker_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())) # Random token per shift, using UUID for uniqueness
    external_tracker_id = Column(String, nullable=False) # ID from external tracking system (e.g., ByteTrack)
    site_id = Column(String, ForeignKey('sites.site_id'), nullable=True) # Which site the worker is at
    session_start = Column(DateTime, default=datetime.now)
    session_end = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    site = relationship('Site', back_populates='workers')
    lift_events = relationship('LiftEvent', back_populates='worker')
    reports = relationship('Report', back_populates='worker_obj') # Renamed to avoid conflict with worker_id column

    __table_args__ = (UniqueConstraint('external_tracker_id', name='_external_tracker_id_uc'),)

    def __repr__(self):
        return f"<Worker(worker_id='{self.worker_id}', external_tracker_id='{self.external_tracker_id}', site_id='{self.site_id}', is_active={self.is_active})>"

class LiftEvent(Base):
    __tablename__ = 'lift_events'

    event_id = Column(Integer, primary_key=True, autoincrement=True)
    worker_id = Column(String, ForeignKey('workers.worker_id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    risk_score = Column(Float, nullable=False)
    safe_lift = Column(Boolean, nullable=False)
    angle_data = Column(JSON, nullable=True) # Store spine/knee/hip vectors as JSON

    worker = relationship('Worker', back_populates='lift_events')

    def __repr__(self):
        return f"<LiftEvent(event_id={self.event_id}, worker_id='{self.worker_id}', risk_score={self.risk_score})>"

class Report(Base):
    __tablename__ = 'reports'

    report_id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String, nullable=False) # employee / union / manager / insurer
    worker_id = Column(String, ForeignKey('workers.worker_id'), nullable=True) # Null if aggregate
    site_id = Column(String, ForeignKey('sites.site_id'), nullable=True) # Null if not site-specific
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    total_lifts = Column(Integer, nullable=False)
    safe_lifts = Column(Integer, nullable=False)
    unsafe_lifts = Column(Integer, nullable=False)
    avg_risk = Column(Float, nullable=False)
    trend_data = Column(JSON, nullable=True) # Store trend data as JSON
    generated_at = Column(DateTime, default=datetime.now)

    worker_obj = relationship('Worker', back_populates='reports')
    site_obj = relationship('Site', back_populates='reports')

    def __repr__(self):
        return f"<Report(report_id={self.report_id}, scope='{self.scope}', worker_id='{self.worker_id}', site_id='{self.site_id}', period='{self.period_start}-{self.period_end}')>"

# Database setup function
def init_db(database_url='sqlite:///./liftbot.db', drop_all=False):
    engine = create_engine(database_url)
    if drop_all:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine) # Creates tables if they don't exist
    Session = sessionmaker(bind=engine)
    return Session, engine

