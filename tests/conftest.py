import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"  # must precede any app import

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User
from app.security import create_access_token, hash_password


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def make_user(email: str, name: str = "Tester") -> str:
    """Creates (or reuses) a user directly and returns a bearer token."""
    with SessionLocal() as db:
        u = db.query(User).filter_by(email=email).first()
        if not u:
            u = User(email=email, full_name=name, password_hash=hash_password("password1"))
            db.add(u)
            db.commit()
        return create_access_token(u.id)


@pytest.fixture()
def admin(client):
    return make_user("owner@example.com", "Owner")


@pytest.fixture()
def event(client, admin):
    """A fresh 2-day event with two halls, owned by `admin`."""
    r = client.post("/api/events", headers=H(admin), json={
        "name": "Test Summit", "edition": "2027", "venue_name": "Expo Mart", "venue_city": "Greater Noida",
        "start_date": "2027-02-08", "end_date": "2027-02-09"})
    ev = r.json()
    for n in ("Hall 4", "Hall 5"):
        client.post(f"/api/events/{ev['id']}/halls", headers=H(admin), json={"name": n})
    return client.get(f"/api/events/{ev['id']}", headers=H(admin)).json()
