
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.types import JSON # Use generic JSON type for broader compatibility
from datetime import datetime, date
import uuid

Base = declarative_base()

class Worker(Base):
    __tablename__ = 'workers'

    worker_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())) # Random token per shift, using UUID for uniqueness
    session_date = Column(Date, default=date.today)
    shift_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    ended_at = Column(DateTime, nullable=True)

    lift_events = relationship('LiftEvent', back_populates='worker')
    reports = relationship('Report', back_populates='worker')

    def __repr__(self):
        return f"<Worker(worker_id='{self.worker_id}', shift_id='{self.shift_id}', session_date='{self.session_date}')>"

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
    shift_id = Column(String, nullable=False)
    total_lifts = Column(Integer, nullable=False)
    safe_lifts = Column(Integer, nullable=False)
    unsafe_lifts = Column(Integer, nullable=False)
    avg_risk = Column(Float, nullable=False)
    generated_at = Column(DateTime, default=datetime.now)

    worker = relationship('Worker', back_populates='reports')

    def __repr__(self):
        return f"<Report(report_id={self.report_id}, scope='{self.scope}', shift_id='{self.shift_id}')>"

# Database setup function
def init_db(database_url='sqlite:///./liftbot.db'):
    engine = create_engine(database_url)
    Base.metadata.create_all(engine) # Creates tables if they don't exist
    Session = sessionmaker(bind=engine)
    return Session, engine


