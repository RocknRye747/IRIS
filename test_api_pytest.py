import os
import socket
import threading
import time
from contextlib import contextmanager
from datetime import datetime, date, timedelta

import pytest
import requests
import uvicorn
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from data_access_layer import DataAccessLayer


TEST_SECRET_KEY = "testsecret"
TEST_API_KEY = "testapikey"


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_server(base_url: str, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    health_url = f"{base_url}/health"
    while time.time() < deadline:
        try:
            response = requests.get(health_url, timeout=1)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.1)
    raise RuntimeError("API server failed to start")


class AuthenticatedClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": api_key})
        self._authenticate()

    def _authenticate(self) -> None:
        response = self.session.post(f"{self.base_url}/auth/token", timeout=5)
        response.raise_for_status()
        token_data = response.json()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token_data['access_token']}",
                "Content-Type": "application/json",
            }
        )

    def _request(self, method: str, path: str, **kwargs):
        kwargs.setdefault("timeout", 5)
        return self.session.request(method, f"{self.base_url}{path}", **kwargs)

    def get(self, path: str, **kwargs):
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self._request("POST", path, **kwargs)

    def delete(self, path: str, **kwargs):
        return self._request("DELETE", path, **kwargs)

    def close(self) -> None:
        self.session.close()


def _create_engine(db_url: str):
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    return create_engine(db_url, connect_args=connect_args)


@contextmanager
def dal_context(db_url: str):
    engine = _create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield DataAccessLayer(session)
    finally:
        session.close()


@pytest.fixture()
def api_server(tmp_path):
    db_path = tmp_path / "liftbot_test.db"
    database_url = f"sqlite:///{db_path}"
    os.environ["SECRET_KEY"] = TEST_SECRET_KEY
    os.environ["API_KEY"] = TEST_API_KEY
    os.environ["TEST_MODE"] = "true"
    os.environ["DATABASE_URL"] = database_url

    port = _get_free_port()
    base_url = f"http://127.0.0.1:{port}"

    config = uvicorn.Config("lift_bot_api:app", host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        _wait_for_server(base_url)
        yield {"base_url": base_url, "api_key": TEST_API_KEY, "db_url": database_url}
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@pytest.fixture()
def api_client(api_server):
    client = AuthenticatedClient(api_server["base_url"], api_server["api_key"])
    try:
        yield client, api_server
    finally:
        client.close()


def test_health_check(api_server):
    response = requests.get(f"{api_server['base_url']}/health", timeout=5)
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint(api_server):
    response = requests.get(f"{api_server['base_url']}/", timeout=5)
    assert response.status_code == 200
    assert "Lift Bot API" in response.json()["message"]


def test_authentication_success(api_server):
    response = requests.post(
        f"{api_server['base_url']}/auth/token",
        headers={"X-API-Key": api_server["api_key"]},
        timeout=5,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data


def test_authentication_failure(api_server):
    response = requests.post(
        f"{api_server['base_url']}/auth/token",
        headers={"X-API-Key": "invalid"},
        timeout=5,
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


def test_create_worker_session(api_client):
    client, _ = api_client
    payload = {"external_tracker_id": "test_tracker_001", "site_name": "warehouse_test"}
    response = client.post("/workers/sessions", json=payload)
    assert response.status_code == 200
    worker_session = response.json()
    assert worker_session["external_tracker_id"] == payload["external_tracker_id"]
    assert worker_session["is_active"] is True
    assert worker_session["site_id"] is not None


def test_create_duplicate_worker_session_returns_existing(api_client):
    client, _ = api_client
    payload = {"external_tracker_id": "test_tracker_002", "site_name": "warehouse_test_2"}
    response1 = client.post("/workers/sessions", json=payload)
    response2 = client.post("/workers/sessions", json=payload)
    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json()["worker_id"] == response2.json()["worker_id"]


def test_create_worker_session_no_site_name(api_client):
    client, _ = api_client
    payload = {"external_tracker_id": "test_tracker_003"}
    response = client.post("/workers/sessions", json=payload)
    assert response.status_code == 200
    worker_session = response.json()
    assert worker_session["site_id"] is None


def test_create_lift_event(api_client):
    client, _ = api_client
    worker = client.post(
        "/workers/sessions", json={"external_tracker_id": "lift_event_worker", "site_name": "test_site"}
    ).json()
    lift_event_data = {
        "worker_id": worker["worker_id"],
        "risk_score": 30.5,
        "safe_lift": False,
        "angle_data": {"back_angle": 120.0, "knee_angle": 150.0},
    }
    response = client.post("/lifts", json=lift_event_data)
    assert response.status_code == 200
    event = response.json()
    assert event["worker_id"] == worker["worker_id"]
    assert event["risk_score"] == pytest.approx(30.5)
    assert event["safe_lift"] is False


def test_create_lift_event_empty_angle_data(api_client):
    client, _ = api_client
    worker = client.post(
        "/workers/sessions",
        json={"external_tracker_id": "lift_event_worker_empty", "site_name": "test_site"},
    ).json()
    response = client.post(
        "/lifts",
        json={"worker_id": worker["worker_id"], "risk_score": 10.0, "safe_lift": True, "angle_data": {}},
    )
    assert response.status_code == 200
    assert response.json()["angle_data"] == {}


def test_create_lift_event_no_angle_data(api_client):
    client, _ = api_client
    worker = client.post(
        "/workers/sessions",
        json={"external_tracker_id": "lift_event_worker_none", "site_name": "test_site"},
    ).json()
    response = client.post(
        "/lifts", json={"worker_id": worker["worker_id"], "risk_score": 5.0, "safe_lift": True, "angle_data": None}
    )
    assert response.status_code == 200
    assert response.json()["angle_data"] == {}


def test_get_employee_report(api_client):
    client, env = api_client
    worker = client.post(
        "/workers/sessions", json={"external_tracker_id": "report_worker", "site_name": "report_site"}
    ).json()
    worker_id = worker["worker_id"]

    client.post(
        "/lifts",
        json={"worker_id": worker_id, "risk_score": 20.0, "safe_lift": False, "angle_data": {}},
    )
    client.post(
        "/lifts",
        json={"worker_id": worker_id, "risk_score": 10.0, "safe_lift": True, "angle_data": {}},
    )

    yesterday = date.today() - timedelta(days=1)
    with dal_context(env["db_url"]) as dal:
        dal.create_lift_event(
            worker_id=worker_id,
            risk_score=50.0,
            safe_lift=False,
            timestamp=datetime.combine(yesterday, datetime.min.time()),
        )

    response = client.get(
        f"/reports/employee/{worker_id}", params={"report_date": date.today().isoformat()}
    )
    assert response.status_code == 200
    report = response.json()
    assert report["total_lifts"] == 2
    assert report["safe_lifts"] == 1
    assert report["unsafe_lifts"] == 1
    assert pytest.approx(report["avg_risk"]) == 15.0


def test_get_employee_report_no_data(api_client):
    client, _ = api_client
    response = client.get(
        "/reports/employee/non_existent_worker", params={"report_date": date.today().isoformat()}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "No data found for this worker on the specified date"


def test_get_aggregate_report(api_client):
    client, env = api_client
    worker_ids = []
    for tracker_id, site in [
        ("agg_worker_1", "agg_site"),
        ("agg_worker_2", "agg_site"),
        ("agg_worker_3", "other_site"),
    ]:
        worker_ids.append(
            client.post("/workers/sessions", json={"external_tracker_id": tracker_id, "site_name": site}).json()[
                "worker_id"
            ]
        )

    client.post(
        "/lifts",
        json={"worker_id": worker_ids[0], "risk_score": 10.0, "safe_lift": True, "angle_data": {}},
    )
    client.post(
        "/lifts",
        json={"worker_id": worker_ids[0], "risk_score": 20.0, "safe_lift": False, "angle_data": {}},
    )
    client.post(
        "/lifts",
        json={"worker_id": worker_ids[1], "risk_score": 5.0, "safe_lift": True, "angle_data": {}},
    )
    client.post(
        "/lifts",
        json={"worker_id": worker_ids[2], "risk_score": 40.0, "safe_lift": False, "angle_data": {}},
    )

    today = date.today().isoformat()
    response_site = client.get(
        "/reports/aggregate",
        params={"site_name": "agg_site", "start_date": today, "end_date": today},
    )
    assert response_site.status_code == 200
    agg_site = response_site.json()
    assert agg_site["total_workers"] == 2
    assert agg_site["total_lifts"] == 3
    assert agg_site["safe_lifts"] == 2
    assert agg_site["unsafe_lifts"] == 1

    response_all = client.get(
        "/reports/aggregate", params={"start_date": today, "end_date": today}
    )
    assert response_all.status_code == 200
    agg_all = response_all.json()
    assert agg_all["total_workers"] == 3
    assert agg_all["total_lifts"] == 4
    assert agg_all["safe_lifts"] == 2
    assert agg_all["unsafe_lifts"] == 2


def test_get_site_statistics(api_client):
    client, env = api_client
    worker = client.post(
        "/workers/sessions", json={"external_tracker_id": "stats_worker", "site_name": "stats_site"}
    ).json()

    client.post(
        "/lifts",
        json={"worker_id": worker["worker_id"], "risk_score": 15.0, "safe_lift": False, "angle_data": {}},
    )
    client.post(
        "/lifts",
        json={"worker_id": worker["worker_id"], "risk_score": 5.0, "safe_lift": True, "angle_data": {}},
    )

    today = date.today().isoformat()
    response = client.get(
        "/reports/sites/stats_site/stats", params={"start_date": today, "end_date": today}
    )
    assert response.status_code == 200
    stats = response.json()
    assert stats["total_workers"] == 1
    assert stats["total_lifts"] == 2
    assert stats["safe_lifts"] == 1
    assert stats["unsafe_lifts"] == 1


def test_get_site_statistics_no_data(api_client):
    client, _ = api_client
    today = date.today().isoformat()
    response = client.get(
        "/reports/sites/non_existent_site/stats",
        params={"start_date": today, "end_date": today},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Site with name 'non_existent_site' not found"


def test_end_worker_session(api_client):
    client, env = api_client
    worker = client.post(
        "/workers/sessions", json={"external_tracker_id": "worker_to_end", "site_name": "end_site"}
    ).json()

    response = client.delete(f"/workers/{worker['worker_id']}")
    assert response.status_code == 200
    assert response.json()["message"] == f"Worker session {worker['worker_id']} ended successfully"

    with dal_context(env["db_url"]) as dal:
        worker_record = dal.get_worker_by_id(worker["worker_id"])
        assert worker_record is not None
        assert worker_record.is_active is False
        assert worker_record.session_end is not None


def test_end_non_existent_worker_session(api_client):
    client, _ = api_client
    response = client.delete("/workers/non_existent_worker_id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Worker not found"


def test_delete_worker_data(api_client):
    client, env = api_client
    worker = client.post(
        "/workers/sessions", json={"external_tracker_id": "worker_to_delete", "site_name": "delete_site"}
    ).json()

    client.post(
        "/lifts",
        json={"worker_id": worker["worker_id"], "risk_score": 20.0, "safe_lift": False, "angle_data": {}},
    )

    response = client.delete(f"/data/worker/{worker['worker_id']}")
    assert response.status_code == 200
    result = response.json()
    assert result["worker_records_deleted"] == 1
    assert result["lift_events_deleted"] >= 1

    with dal_context(env["db_url"]) as dal:
        assert dal.get_worker_by_id(worker["worker_id"]) is None
        lift_events = dal.get_lift_events_by_worker_and_date(worker["worker_id"], date.today())
        assert len(lift_events) == 0
