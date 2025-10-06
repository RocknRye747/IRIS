from fastapi import FastAPI, HTTPException, Depends, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
import json
import logging
from passlib.context import CryptContext
from jose import JWTError, jwt
import os

# Import our database models and utilities
from database import init_db, Worker, LiftEvent, Report

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Lift Bot API",
    description="AI-powered ergonomics monitoring platform for warehouse and retail environments",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# API Key configuration
API_KEY_NAME = "X-API-Key"
API_KEY = os.getenv("API_KEY", "your-api-key-change-in-production")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security schemes
security = HTTPBearer()
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Initialize database
Session, engine = init_db()

# Pydantic Models for API

class LiftEventCreate(BaseModel):
    """Model for creating a new lift event"""
    worker_id: str = Field(..., description="Anonymous worker ID")
    risk_score: float = Field(..., ge=0, le=100, description="Risk score from 0-100")
    safe_lift: bool = Field(..., description="Whether the lift was classified as safe")
    angle_data: Optional[Dict[str, Any]] = Field(None, description="Detailed angle measurements")

class LiftEventResponse(BaseModel):
    """Model for lift event response"""
    id: int
    worker_id: str
    timestamp: datetime
    risk_score: float
    safe_lift: bool
    angle_data: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True

class WorkerSessionCreate(BaseModel):
    """Model for creating a worker session"""
    external_tracker_id: str = Field(..., description="External tracking system ID")
    site_id: Optional[str] = Field(None, description="Site identifier")

class WorkerSessionResponse(BaseModel):
    """Model for worker session response"""
    worker_id: str
    external_tracker_id: str
    session_start: datetime
    site_id: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True

class EmployeeReportResponse(BaseModel):
    """Model for employee report response"""
    worker_id: str
    date: date
    total_lifts: int
    safe_lifts: int
    unsafe_lifts: int
    avg_risk: float
    improvement_vs_last_week: Optional[str] = None

class AggregateReportResponse(BaseModel):
    """Model for aggregate report response"""
    period: str
    total_workers: int
    total_lifts: int
    safe_lifts: int
    unsafe_lifts: int
    avg_risk: float
    trend: Optional[str] = None

class SiteStatsResponse(BaseModel):
    """Model for site statistics response"""
    site_id: str
    period: str
    total_workers: int
    total_lifts: int
    safe_lifts: int
    unsafe_lifts: int
    avg_risk: float

class Token(BaseModel):
    """Model for authentication token"""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Model for token data"""
    username: Optional[str] = None

# Dependency functions

def get_db():
    """Dependency to get database session"""
    db = Session()
    try:
        yield db
    finally:
        db.close()

def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify API key for authentication"""
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return api_key

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# API Endpoints

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Lift Bot API",
        "version": "1.0.0",
        "description": "AI-powered ergonomics monitoring platform",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}

# Authentication Endpoints

@app.post("/auth/token", response_model=Token, tags=["Authentication"])
async def login_for_access_token(api_key: str = Depends(verify_api_key)):
    """Generate access token using API key"""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": "lift_bot_user"}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Data Ingestion Endpoints

@app.post("/lifts", response_model=LiftEventResponse, tags=["Data Ingestion"])
async def create_lift_event(
    lift_event: LiftEventCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Create a new lift event record"""
    try:
        # Create new lift event
        db_lift_event = LiftEvent(
            worker_id=lift_event.worker_id,
            timestamp=datetime.utcnow(),
            risk_score=lift_event.risk_score,
            safe_lift=lift_event.safe_lift,
            angle_data=json.dumps(lift_event.angle_data) if lift_event.angle_data else None
        )
        
        db.add(db_lift_event)
        db.commit()
        db.refresh(db_lift_event)
        
        logger.info(f"Created lift event for worker {lift_event.worker_id}")
        
        # Convert angle_data back to dict for response
        response_data = LiftEventResponse.from_orm(db_lift_event)
        if db_lift_event.angle_data:
            response_data.angle_data = json.loads(db_lift_event.angle_data)
        
        return response_data
        
    except Exception as e:
        logger.error(f"Error creating lift event: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create lift event"
        )

@app.post("/workers/sessions", response_model=WorkerSessionResponse, tags=["Worker Management"])
async def create_worker_session(
    worker_session: WorkerSessionCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Create or retrieve a worker session"""
    try:
        # Check if worker already exists for this external tracker ID
        existing_worker = db.query(Worker).filter(
            Worker.external_tracker_id == worker_session.external_tracker_id,
            Worker.is_active == True
        ).first()
        
        if existing_worker:
            return WorkerSessionResponse.from_orm(existing_worker)
        
        # Create new worker session
        db_worker = Worker(
            external_tracker_id=worker_session.external_tracker_id,
            site_id=worker_session.site_id,
            session_start=datetime.utcnow(),
            is_active=True
        )
        
        db.add(db_worker)
        db.commit()
        db.refresh(db_worker)
        
        logger.info(f"Created worker session {db_worker.worker_id}")
        
        return WorkerSessionResponse.from_orm(db_worker)
        
    except Exception as e:
        logger.error(f"Error creating worker session: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create worker session"
        )

@app.delete("/workers/{worker_id}", tags=["Worker Management"])
async def end_worker_session(
    worker_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """End a worker session"""
    try:
        worker = db.query(Worker).filter(Worker.worker_id == worker_id).first()
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Worker not found"
            )
        
        worker.is_active = False
        worker.session_end = datetime.utcnow()
        db.commit()
        
        logger.info(f"Ended worker session {worker_id}")
        
        return {"message": f"Worker session {worker_id} ended successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending worker session: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end worker session"
        )

# Reporting Endpoints

@app.get("/reports/employee/{worker_id}", response_model=EmployeeReportResponse, tags=["Reports"])
async def get_employee_report(
    worker_id: str,
    report_date: Optional[date] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Get employee-specific report for a given date"""
    try:
        if not report_date:
            report_date = date.today()
        
        # Query lift events for the worker on the specified date
        lift_events = db.query(LiftEvent).filter(
            LiftEvent.worker_id == worker_id,
            func.date(LiftEvent.timestamp) == report_date
        ).all()
        
        if not lift_events:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No data found for this worker on the specified date"
            )
        
        # Calculate statistics
        total_lifts = len(lift_events)
        safe_lifts = sum(1 for event in lift_events if event.safe_lift)
        unsafe_lifts = total_lifts - safe_lifts
        avg_risk = sum(event.risk_score for event in lift_events) / total_lifts
        
        # Calculate improvement vs last week (placeholder logic)
        last_week_date = report_date - timedelta(days=7)
        last_week_events = db.query(LiftEvent).filter(
            LiftEvent.worker_id == worker_id,
            func.date(LiftEvent.timestamp) == last_week_date
        ).all()
        
        improvement_vs_last_week = None
        if last_week_events:
            last_week_avg_risk = sum(event.risk_score for event in last_week_events) / len(last_week_events)
            improvement = ((last_week_avg_risk - avg_risk) / last_week_avg_risk) * 100
            improvement_vs_last_week = f"{improvement:+.1f}%"
        
        return EmployeeReportResponse(
            worker_id=worker_id,
            date=report_date,
            total_lifts=total_lifts,
            safe_lifts=safe_lifts,
            unsafe_lifts=unsafe_lifts,
            avg_risk=round(avg_risk, 2),
            improvement_vs_last_week=improvement_vs_last_week
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating employee report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate employee report"
        )

@app.get("/reports/aggregate", response_model=AggregateReportResponse, tags=["Reports"])
async def get_aggregate_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    site_id: Optional[str] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Get aggregate report for a date range and optional site"""
    try:
        if not start_date:
            start_date = date.today() - timedelta(days=7)
        if not end_date:
            end_date = date.today()
        
        # Build query
        query = db.query(LiftEvent).filter(
            func.date(LiftEvent.timestamp) >= start_date,
            func.date(LiftEvent.timestamp) <= end_date
        )
        
        # Filter by site if provided
        if site_id:
            query = query.join(Worker).filter(Worker.site_id == site_id)
        
        lift_events = query.all()
        
        if not lift_events:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No data found for the specified period"
            )
        
        # Calculate statistics
        total_lifts = len(lift_events)
        safe_lifts = sum(1 for event in lift_events if event.safe_lift)
        unsafe_lifts = total_lifts - safe_lifts
        avg_risk = sum(event.risk_score for event in lift_events) / total_lifts
        
        # Count unique workers
        unique_workers = len(set(event.worker_id for event in lift_events))
        
        # Calculate trend (placeholder logic)
        period_str = f"{start_date} to {end_date}"
        trend = "stable"  # This would be calculated based on historical data
        
        return AggregateReportResponse(
            period=period_str,
            total_workers=unique_workers,
            total_lifts=total_lifts,
            safe_lifts=safe_lifts,
            unsafe_lifts=unsafe_lifts,
            avg_risk=round(avg_risk, 2),
            trend=trend
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating aggregate report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate aggregate report"
        )

@app.get("/reports/sites/{site_id}/stats", response_model=SiteStatsResponse, tags=["Reports"])
async def get_site_statistics(
    site_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Get statistics for a specific site"""
    try:
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        
        # Query lift events for the site
        lift_events = db.query(LiftEvent).join(Worker).filter(
            Worker.site_id == site_id,
            func.date(LiftEvent.timestamp) >= start_date,
            func.date(LiftEvent.timestamp) <= end_date
        ).all()
        
        if not lift_events:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No data found for this site in the specified period"
            )
        
        # Calculate statistics
        total_lifts = len(lift_events)
        safe_lifts = sum(1 for event in lift_events if event.safe_lift)
        unsafe_lifts = total_lifts - safe_lifts
        avg_risk = sum(event.risk_score for event in lift_events) / total_lifts
        unique_workers = len(set(event.worker_id for event in lift_events))
        
        period_str = f"{start_date} to {end_date}"
        
        return SiteStatsResponse(
            site_id=site_id,
            period=period_str,
            total_workers=unique_workers,
            total_lifts=total_lifts,
            safe_lifts=safe_lifts,
            unsafe_lifts=unsafe_lifts,
            avg_risk=round(avg_risk, 2)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating site statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate site statistics"
        )

# Privacy and Data Management Endpoints

@app.delete("/data/worker/{worker_id}", tags=["Privacy"])
async def delete_worker_data(
    worker_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Delete all data for a specific worker (GDPR compliance)"""
    try:
        # Delete lift events
        lift_events_deleted = db.query(LiftEvent).filter(
            LiftEvent.worker_id == worker_id
        ).delete()
        
        # Delete worker record
        worker_deleted = db.query(Worker).filter(
            Worker.worker_id == worker_id
        ).delete()
        
        db.commit()
        
        logger.info(f"Deleted data for worker {worker_id}: {lift_events_deleted} lift events, {worker_deleted} worker record")
        
        return {
            "message": f"All data for worker {worker_id} has been deleted",
            "lift_events_deleted": lift_events_deleted,
            "worker_records_deleted": worker_deleted
        }
        
    except Exception as e:
        logger.error(f"Error deleting worker data: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete worker data"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
