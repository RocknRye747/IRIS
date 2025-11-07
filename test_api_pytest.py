import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date, timedelta
import os

# Import app and database components
from lift_bot_api import app, get_db, get_dal, SECRET_KEY, ALGORITHM, API_KEY
from database import Base, Site, Worker, LiftEvent, Report
from data_access_layer import DataAccessLayer

# Use a test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_liftbot.db"

# Create a test engine and session
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the get_db dependency for testing
@pytest.fixture(name="db_session")
def db_session_fixture():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine) # Clean up after tests

@pytest.fixture(name="client")
def client_fixture(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides = {}

@pytest.fixture(name="auth_headers")
def auth_headers_fixture(client):
    response = client.post("/auth/token", headers={"X-API-Key": API_KEY})
    assert response.status_code == 200
    token_data = response.json()
    return {
        "X-API-Key": API_KEY,
        "Authorization": f"Bearer {token_data['access_token']}",
        "Content-Type": "application/json"
    }

# --- Test Cases ---

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Lift Bot API" in response.json()["message"]

def test_authentication_success(client):
    response = client.post("/auth/token", headers={"X-API-Key": API_KEY})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_authentication_failure(client):
    response = client.post("/auth/token", headers={"X-API-Key": "invalid_key"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"

def test_create_worker_session(client, auth_headers):
    worker_data = {
        "external_tracker_id": "test_tracker_001",
        "site_name": "warehouse_test"
    }
    response = client.post("/workers/sessions", headers=auth_headers, json=worker_data)
    assert response.status_code == 200
    worker_session = response.json()
    assert "worker_id" in worker_session
    assert worker_session["external_tracker_id"] == "test_tracker_001"
    assert worker_session["is_active"] == True
    assert worker_session["site_id"] is not None

def test_create_duplicate_worker_session_returns_existing(client, auth_headers):
    worker_data = {
        "external_tracker_id": "test_tracker_002",
        "site_name": "warehouse_test_2"
    }
    # First creation
    response1 = client.post("/workers/sessions", headers=auth_headers, json=worker_data)
    assert response1.status_code == 200
    worker_session1 = response1.json()

    # Second creation with same external_tracker_id
    response2 = client.post("/workers/sessions", headers=auth_headers, json=worker_data)
    assert response2.status_code == 200
    worker_session2 = response2.json()

    assert worker_session1["worker_id"] == worker_session2["worker_id"]
    assert worker_session1["external_tracker_id"] == worker_session2["external_tracker_id"]
    assert worker_session2["is_active"] == True

def test_create_worker_session_no_site_name(client, auth_headers):
    worker_data = {
        "external_tracker_id": "test_tracker_003"
    }
    response = client.post("/workers/sessions", headers=auth_headers, json=worker_data)
    assert response.status_code == 200
    worker_session = response.json()
    assert "worker_id" in worker_session
    assert worker_session["external_tracker_id"] == "test_tracker_003"
    assert worker_session["is_active"] == True
    assert worker_session["site_id"] is None

def test_create_lift_event(client, auth_headers):
    # First create a worker session
    worker_data = {
        "external_tracker_id": "lift_event_worker",
        "site_name": "test_site_for_lifts"
    }
    worker_response = client.post("/workers/sessions", headers=auth_headers, json=worker_data)
    assert worker_response.status_code == 200
    worker_id = worker_response.json()["worker_id"]

    lift_event_data = {
        "worker_id": worker_id,
        "risk_score": 30.5,
        "safe_lift": False,
        "angle_data": {"back_angle": 120.0, "knee_angle": 150.0}
    }
    response = client.post("/lifts", headers=auth_headers, json=lift_event_data)
    assert response.status_code == 200
    event_data = response.json()
    assert "event_id" in event_data
    assert event_data["worker_id"] == worker_id
    assert event_data["risk_score"] == 30.5
    assert event_data["safe_lift"] == False
    assert event_data["angle_data"] == {"back_angle": 120.0, "knee_angle": 150.0}

def test_create_lift_event_empty_angle_data(client, auth_headers):
    # First create a worker session
    worker_data = {
        "external_tracker_id": "lift_event_worker_empty_angles",
        "site_name": "test_site_for_lifts"
    }
    worker_response = client.post("/workers/sessions", headers=auth_headers, json=worker_data)
    assert worker_response.status_code == 200
    worker_id = worker_response.json()["worker_id"]

    lift_event_data = {
        "worker_id": worker_id,
        "risk_score": 10.0,
        "safe_lift": True,
        "angle_data": {}
    }
    response = client.post("/lifts", headers=auth_headers, json=lift_event_data)
    assert response.status_code == 200
    event_data = response.json()
    assert "event_id" in event_data
    assert event_data["worker_id"] == worker_id
    assert event_data["risk_score"] == 10.0
    assert event_data["safe_lift"] == True
    assert event_data["angle_data"] == {}

def test_create_lift_event_no_angle_data(client, auth_headers):
    # First create a worker session
    worker_data = {
        "external_tracker_id": "lift_event_worker_no_angles",
        "site_name": "test_site_for_lifts"
    }
    worker_response = client.post("/workers/sessions", headers=auth_headers, json=worker_data)
    assert worker_response.status_code == 200
    worker_id = worker_response.json()["worker_id"]

    lift_event_data = {
        "worker_id": worker_id,
        "risk_score": 5.0,
        "safe_lift": True,
        "angle_data": None
    }
    response = client.post("/lifts", headers=auth_headers, json=lift_event_data)
    assert response.status_code == 200
    event_data = response.json()
    assert "event_id" in event_data
    assert event_data["worker_id"] == worker_id
    assert event_data["risk_score"] == 5.0
    assert event_data["safe_lift"] == True
    assert event_data["angle_data"] == {}

def test_get_employee_report(client, auth_headers):
    # Create worker and lift events
    worker_data = {
        "external_tracker_id": "report_worker",
        "site_name": "report_site"
    }
    worker_response = client.post("/workers/sessions", headers=auth_headers, json=worker_data)
    worker_id = worker_response.json()["worker_id"]

    today = date.today()
    yesterday = today - timedelta(days=1)

    # Lift event for today
    client.post("/lifts", headers=auth_headers, json={
        "worker_id": worker_id,
        "risk_score": 20.0,
        "safe_lift": False,
        "angle_data": {}
    })
    client.post("/lifts", headers=auth_headers, json={
        "worker_id": worker_id,
        "risk_score": 10.0,
        "safe_lift": True,
        "angle_data": {}
    })

    # Lift event for yesterday (should not be in today's report)
    dal = DataAccessLayer(client.app.dependency_overrides[get_db]().__next__())
    dal.create_lift_event(worker_id=worker_id, risk_score=50.0, safe_lift=False, timestamp=datetime.combine(yesterday, datetime.min.time()))

    response = client.get(f"/reports/employee/{worker_id}?report_date={today.isoformat()}", headers=auth_headers)
    assert response.status_code == 200
    report = response.json()
    assert report["worker_id"] == worker_id
    assert report["date"] == today.isoformat()
    assert report["total_lifts"] == 2
    assert report["safe_lifts"] == 1
    assert report["unsafe_lifts"] == 1
    assert pytest.approx(report["avg_risk"]) == 15.0

def test_get_employee_report_no_data(client, auth_headers):
    # Use a worker ID that has no lift events
    response = client.get(f"/reports/employee/non_existent_worker?report_date={date.today().isoformat()}", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "No data found for this worker on the specified date"

def test_get_aggregate_report(client, auth_headers):
    # Create workers and lift events for aggregate report
    worker_data1 = {"external_tracker_id": "agg_worker_1", "site_name": "agg_site"}
    worker_data2 = {"external_tracker_id": "agg_worker_2", "site_name": "agg_site"}
    worker_data3 = {"external_tracker_id": "agg_worker_3", "site_name": "other_site"}

    worker_id1 = client.post("/workers/sessions", headers=auth_headers, json=worker_data1).json()["worker_id"]
    worker_id2 = client.post("/workers/sessions", headers=auth_headers, json=worker_data2).json()["worker_id"]
    worker_id3 = client.post("/workers/sessions", headers=auth_headers, json=worker_data3).json()["worker_id"]

    today = date.today()
    dal = DataAccessLayer(client.app.dependency_overrides[get_db]().__next__())

    # Lifts for agg_worker_1 (agg_site)
    dal.create_lift_event(worker_id=worker_id1, risk_score=10.0, safe_lift=True)
    dal.create_lift_event(worker_id=worker_id1, risk_score=20.0, safe_lift=False)

    # Lifts for agg_worker_2 (agg_site)
    dal.create_lift_event(worker_id=worker_id2, risk_score=5.0, safe_lift=True)

    # Lifts for agg_worker_3 (other_site) - should not be in agg_site report
    dal.create_lift_event(worker_id=worker_id3, risk_score=40.0, safe_lift=False)

    # Test aggregate report for 'agg_site'
    response = client.get(f"/reports/aggregate?site_name=agg_site&start_date={today.isoformat()}&end_date={today.isoformat()}", headers=auth_headers)
    assert response.status_code == 200
    report = response.json()
    assert report["total_workers"] == 2
    assert report["total_lifts"] == 3
    assert report["safe_lifts"] == 2
    assert report["unsafe_lifts"] == 1
    assert report["avg_risk"] == pytest.approx(round((10.0 + 20.0 + 5.0) / 3, 2))

    # Test aggregate report for all sites
    response_all = client.get(f"/reports/aggregate?start_date={today.isoformat()}&end_date={today.isoformat()}", headers=auth_headers)
    assert response_all.status_code == 200
    report_all = response_all.json()
    assert report_all["total_workers"] == 3
    assert report_all["total_lifts"] == 4
    assert report_all["safe_lifts"] == 2
    assert report_all["unsafe_lifts"] == 2
    assert report_all["avg_risk"] == pytest.approx((10.0 + 20.0 + 5.0 + 40.0) / 4)

def test_get_site_statistics(client, auth_headers):
    # Create worker and lift events for site statistics
    worker_data = {"external_tracker_id": "stats_worker", "site_name": "stats_site"}
    worker_id = client.post("/workers/sessions", headers=auth_headers, json=worker_data).json()["worker_id"]

    today = date.today()
    dal = DataAccessLayer(client.app.dependency_overrides[get_db]().__next__())

    dal.create_lift_event(worker_id=worker_id, risk_score=15.0, safe_lift=False)
    dal.create_lift_event(worker_id=worker_id, risk_score=5.0, safe_lift=True)

    response = client.get(f"/reports/sites/stats_site/stats?start_date={today.isoformat()}&end_date={today.isoformat()}", headers=auth_headers)
    assert response.status_code == 200
    stats = response.json()
    assert stats["site_id"] is not None
    assert stats["total_workers"] == 1
    assert stats["total_lifts"] == 2
    assert stats["safe_lifts"] == 1
    assert stats["unsafe_lifts"] == 1
    assert pytest.approx(stats["avg_risk"]) == 10.0

def test_get_site_statistics_no_data(client, auth_headers):
    response = client.get(f"/reports/sites/non_existent_site/stats?start_date={date.today().isoformat()}&end_date={date.today().isoformat()}", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Site with name 'non_existent_site' not found"

def test_end_worker_session(client, auth_headers):
    worker_data = {"external_tracker_id": "worker_to_end", "site_name": "end_session_site"}
    worker_response = client.post("/workers/sessions", headers=auth_headers, json=worker_data)
    worker_id = worker_response.json()["worker_id"]

    response = client.delete(f"/workers/{worker_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["message"] == f"Worker session {worker_id} ended successfully"

    # Verify session is inactive
    dal = DataAccessLayer(client.app.dependency_overrides[get_db]().__next__())
    worker = dal.get_worker_by_id(worker_id)
    assert worker is not None
    assert worker.is_active == False
    assert worker.session_end is not None

def test_end_non_existent_worker_session(client, auth_headers):
    response = client.delete(f"/workers/non_existent_worker_id", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Worker not found"

def test_delete_worker_data(client, auth_headers):
    # Create worker and some data
    worker_data = {"external_tracker_id": "worker_to_delete", "site_name": "delete_site"}
    worker_response = client.post("/workers/sessions", headers=auth_headers, json=worker_data)
    worker_id = worker_response.json()["worker_id"]

    client.post("/lifts", headers=auth_headers, json={
        "worker_id": worker_id,
        "risk_score": 20.0,
        "safe_lift": False,
        "angle_data": {}
    })

    response = client.delete(f"/data/worker/{worker_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["message"] == f"All data for worker {worker_id} has been deleted"
    assert response.json()["lift_events_deleted"] >= 1
    assert response.json()["worker_records_deleted"] == 1

    # Verify data is gone
    dal = DataAccessLayer(client.app.dependency_overrides[get_db]().__next__())
    worker = dal.get_worker_by_id(worker_id)
    assert worker is None
    lift_events = dal.get_lift_events_by_worker_and_date(worker_id, date.today())
    assert len(lift_events) == 0

