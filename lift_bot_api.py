from fastapi import FastAPI, HTTPException, Depends, status, Security
from fastapi.security import HTTPBearer, APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
import json
import logging
import uvicorn
from passlib.context import CryptContext
from jose import JWTError, jwt
import os
from contextlib import asynccontextmanager

# Import our database models and utilities
from database import init_db, Base, Site, Worker, LiftEvent, Report
from data_access_layer import DataAccessLayer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security configuration
def _get_required_setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Environment variable '{name}' must be set before starting the Lift Bot API."
        )
    return value


SECRET_KEY = _get_required_setting("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# API Key configuration
API_KEY_NAME = "X-API-Key"
API_KEY = _get_required_setting("API_KEY")

# Password hashing (not directly used for API key, but good practice for user management)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security schemes
security = HTTPBearer()
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Initialize database

def _initialize_database():
    """Configure the SQLAlchemy session factory from the current environment."""

    database_url = os.getenv("DATABASE_URL", "sqlite:///./liftbot.db")
    return init_db(database_url=database_url, drop_all=False)


SessionLocal, engine = _initialize_database()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic: Ensure tables are created and handle test mode reset
    global SessionLocal, engine
    SessionLocal, engine = _initialize_database()

    if os.getenv("TEST_MODE") == "true":
        logger.info("TEST_MODE is true. Dropping all database tables.")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables dropped and recreated for testing.")
    else:
        # This will create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables ensured to be created.")
    
    # Yield control to the application
    yield

    # Shutdown logic (optional)
    logger.info("Shutting down application...")

# Initialize FastAPI app
app = FastAPI(
    title="Lift Bot API",
    description="AI-powered ergonomics monitoring platform for warehouse and retail environments",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models for API

class LiftEventCreate(BaseModel):
    """Model for creating a new lift event"""
    worker_id: str = Field(..., description="Anonymous worker ID")
    risk_score: float = Field(..., ge=0, le=100, description="Risk score from 0-100")
    safe_lift: bool = Field(..., description="Whether the lift was classified as safe")
    angle_data: Optional[Dict[str, Any]] = Field(None, description="Detailed angle measurements")

class LiftEventResponse(BaseModel):
    """Model for lift event response"""
    id: int = Field(..., alias="event_id") # Map event_id from SQLAlchemy to id
    worker_id: str
    timestamp: datetime
    risk_score: float
    safe_lift: bool
    angle_data: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            date: lambda d: d.isoformat(),
        }

class WorkerSessionCreate(BaseModel):
    """Model for creating a worker session"""
    external_tracker_id: str = Field(..., description="External tracking system ID")
    site_name: Optional[str] = Field(None, description="Site name for the worker session")

class WorkerSessionResponse(BaseModel):
    """Model for worker session response"""
    worker_id: str
    external_tracker_id: str
    site_id: Optional[str]
    session_start: datetime
    session_end: Optional[datetime] = None
    is_active: bool

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            date: lambda d: d.isoformat(),
        }

class EmployeeReportResponse(BaseModel):
    """Model for employee report response"""
    worker_id: str
    date: date
    total_lifts: int
    safe_lifts: int
    unsafe_lifts: int
    avg_risk: float
    improvement_vs_last_week: Optional[str] = None

    class Config:
        json_encoders = {
            date: lambda d: d.isoformat(),
        }

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
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_dal(db: Session = Depends(get_db)) -> DataAccessLayer:
    """Dependency to get DataAccessLayer instance"""
    return DataAccessLayer(db)

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
    dal: DataAccessLayer = Depends(get_dal),
    api_key: str = Depends(verify_api_key)
):
    """Create a new lift event record"""
    try:
        # Ensure angle_data is a dictionary, even if None is provided
        processed_angle_data = lift_event.angle_data if lift_event.angle_data is not None else {}

        db_lift_event = dal.create_lift_event(
            worker_id=lift_event.worker_id,
            risk_score=lift_event.risk_score,
            safe_lift=lift_event.safe_lift,
            angle_data=processed_angle_data
        )
        
        # Convert angle_data back to dict for response if it was stored as JSON string
        response_data = LiftEventResponse.model_validate(db_lift_event)
        if isinstance(response_data.angle_data, str):
            response_data.angle_data = json.loads(response_data.angle_data)
        
        logger.info(f"Created lift event for worker {lift_event.worker_id}")
        return response_data
        
    except Exception as e:
        logger.error(f"Error creating lift event: {e}. Lift event data: {lift_event.model_dump_json()}")
        dal.db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create lift event"
        )

@app.post("/workers/sessions", response_model=WorkerSessionResponse, tags=["Worker Management"])
async def create_worker_session(
    worker_session: WorkerSessionCreate,
    dal: DataAccessLayer = Depends(get_dal),
    api_key: str = Depends(verify_api_key)
):
    """Create or retrieve a worker session"""
    try:
        site_id = None
        if worker_session.site_name:
            site = dal.get_site_by_name(worker_session.site_name)
            if not site:
                site = dal.create_site(worker_session.site_name)
            site_id = site.site_id

        # Attempt to get an existing active worker session
        db_worker = dal.get_active_worker_by_external_id(worker_session.external_tracker_id)

        if db_worker:
            logger.info(f"Returning existing active worker session {db_worker.worker_id} for external_tracker_id {worker_session.external_tracker_id}")
            return WorkerSessionResponse.model_validate(db_worker)

        # If no active session, create a new one
        db_worker = dal.create_worker_session(
            external_tracker_id=worker_session.external_tracker_id,
            site_id=site_id
        )

        
        logger.info(f"Created worker session {db_worker.worker_id}")
        return WorkerSessionResponse.model_validate(db_worker)
        
    except Exception as e:
        logger.error(f"Error creating worker session: {e}")
        dal.db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create worker session"
        )

@app.delete("/workers/{worker_id}", tags=["Worker Management"])
async def end_worker_session(
    worker_id: str,
    dal: DataAccessLayer = Depends(get_dal),
    api_key: str = Depends(verify_api_key)
):
    """End a worker session"""
    try:
        worker = dal.end_worker_session(worker_id)
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Worker not found"
            )
        
        logger.info(f"Ended worker session {worker_id}")
        return {"message": f"Worker session {worker_id} ended successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending worker session: {e}")
        dal.db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end worker session"
        )

# Reporting Endpoints

@app.get("/reports/employee/{worker_id}", response_model=EmployeeReportResponse, tags=["Reports"])
async def get_employee_report(
    worker_id: str,
    report_date: Optional[date] = None,
    dal: DataAccessLayer = Depends(get_dal),
    api_key: str = Depends(verify_api_key)
):
    """Generate a daily report for a specific worker"""
    try:
        target_date = report_date if report_date else date.today()
        
        # 1. Get all lift events for the worker on the target date
        lift_events = dal.get_lift_events_by_worker_and_date(worker_id, target_date)
        
        if not lift_events:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No data found for this worker on the specified date"
            )
            
        # 2. Calculate metrics
        total_lifts = len(lift_events)
        safe_lifts = sum(1 for event in lift_events if event.safe_lift)
        unsafe_lifts = total_lifts - safe_lifts
        avg_risk = sum(event.risk_score for event in lift_events) / total_lifts if total_lifts > 0 else 0.0
        
        # 3. Generate report response
        report_data = {
            "worker_id": worker_id,
            "date": target_date,
            "total_lifts": total_lifts,
            "safe_lifts": safe_lifts,
            "unsafe_lifts": unsafe_lifts,
            "avg_risk": round(avg_risk, 2),
            "improvement_vs_last_week": "N/A (Feature not yet implemented)"
        }
        
        return EmployeeReportResponse.model_validate(report_data)
        
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
    site_name: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    dal: DataAccessLayer = Depends(get_dal),
    api_key: str = Depends(verify_api_key)
):
    """Generate an aggregate report for a site or the entire system over a period"""
    try:
        # Default to today if no dates are provided
        today = date.today()
        start = start_date if start_date else today
        end = end_date if end_date else today
        
        # 1. Get all lift events and workers in the scope/period
        metrics = dal.get_aggregate_metrics(site_name, start, end)
        
        # 2. Generate report response
        period_str = f"{start.isoformat()} to {end.isoformat()}"
        if start == end:
            period_str = start.isoformat()
            
        report_data = {
            "period": period_str,
            "total_workers": metrics["total_workers"],
            "total_lifts": metrics["total_lifts"],
            "safe_lifts": metrics["safe_lifts"],
            "unsafe_lifts": metrics["unsafe_lifts"],
            "avg_risk": round(metrics["avg_risk"], 2) if metrics["total_lifts"] > 0 else 0.0,
            "trend": "N/A (Feature not yet implemented)"
        }
        
        return AggregateReportResponse.model_validate(report_data)
        
    except Exception as e:
        logger.error(f"Error generating aggregate report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate aggregate report"
        )

@app.get("/reports/sites/{site_name}/stats", response_model=SiteStatsResponse, tags=["Reports"])
async def get_site_statistics(
    site_name: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    dal: DataAccessLayer = Depends(get_dal),
    api_key: str = Depends(verify_api_key)
):
    """Generate statistics for a specific site over a period"""
    try:
        # 1. Verify site existence
        site = dal.get_site_by_name(site_name)
        if not site:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Site with name '{site_name}' not found"
            )
            
        # Default to today if no dates are provided
        today = date.today()
        start = start_date if start_date else today
        end = end_date if end_date else today
        
        # 2. Get aggregate metrics for the site
        metrics = dal.get_aggregate_metrics(site_name, start, end)
        
        # 3. Generate response
        period_str = f"{start.isoformat()} to {end.isoformat()}"
        if start == end:
            period_str = start.isoformat()
            
        stats_data = {
            "site_id": site.site_id,
            "period": period_str,
            "total_workers": metrics["total_workers"],
            "total_lifts": metrics["total_lifts"],
            "safe_lifts": metrics["safe_lifts"],
            "unsafe_lifts": metrics["unsafe_lifts"],
            "avg_risk": round(metrics["avg_risk"], 2) if metrics["total_lifts"] > 0 else 0.0
        }
        
        return SiteStatsResponse.model_validate(stats_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating site statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate site statistics"
        )

@app.delete("/data/worker/{worker_id}", tags=["Privacy"])
async def delete_worker_data(
    worker_id: str,
    dal: DataAccessLayer = Depends(get_dal),
    api_key: str = Depends(verify_api_key)
):
    """Delete all data for a specific worker (GDPR compliance)"""
    try:
        deleted_counts = dal.delete_worker_data(worker_id)
        if deleted_counts["worker_records_deleted"] == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
        
        logger.info(f"Deleted data for worker {worker_id}: {deleted_counts['lift_events_deleted']} lift events, {deleted_counts['worker_records_deleted']} worker record")
        
        return {
            "message": f"All data for worker {worker_id} has been deleted",
            "lift_events_deleted": deleted_counts["lift_events_deleted"],
            "worker_records_deleted": deleted_counts["worker_records_deleted"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting worker data: {e}")
        dal.db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete worker data"
        )


# Main entry point for running the FastAPI app with Uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
