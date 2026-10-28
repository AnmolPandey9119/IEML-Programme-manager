from datetime import time


import pytest
from fastapi.testclient import TestClient

from app import models as m
from app.database import SessionLocal
from app.main import app


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_full_phase1_flow(c):
    # --- first-time setup (no self-registration afterwards)
    assert c.get("/api/auth/setup-status").json()["needs_setup"] is True
    assert c.post("/api/auth/login", json={"email": "a@example.com", "password": "whatever1"}).status_code == 401
    r = c.post("/api/auth/setup", json={"email": "A@Example.com", "password": "password1", "full_name": "Anmol"})
    assert r.status_code == 200
    admin = r.json()["access_token"]
    assert c.get("/api/auth/setup-status").json()["needs_setup"] is False
    assert c.post("/api/auth/setup", json={"email": "x@example.com", "password": "password1", "full_name": "X"}).status_code == 403
    assert c.post("/api/auth/login", json={"email": "a@example.com", "password": "password1"}).status_code == 200
    assert c.get("/api/events").status_code == 401

    # --- create event with 3 days
    r = c.post("/api/events", headers=H(admin), json={
        "name": "Bharat Sustainability Summit", "edition": "2027", "venue_name": "Expo Mart",
        "venue_city": "Greater Noida", "start_date": "2027-02-08", "end_date": "2027-02-10"})
    assert r.status_code == 201
    ev = r.json()
    eid = ev["id"]
    assert [d["label"] for d in ev["days"]][0] == "Day 1 — Monday, Feb 8"
    assert len(ev["days"]) == 3 and ev["my_role"] == "admin" and ev["status"] == "draft"
    assert c.post("/api/events", headers=H(admin), json={"name": "Bad", "start_date": "2027-02-10", "end_date": "2027-02-08"}).status_code == 400

    # --- halls: add, duplicate, reorder, rename, delete
    h1 = c.post(f"/api/events/{eid}/halls", headers=H(admin), json={"name": "Hall 4"}).json()
    h2 = c.post(f"/api/events/{eid}/halls", headers=H(admin), json={"name": "Main Auditorium"}).json()
    assert c.post(f"/api/events/{eid}/halls", headers=H(admin), json={"name": "hall 4"}).status_code == 409
    r = c.put(f"/api/events/{eid}/halls/order", headers=H(admin), json={"ids": [h2["id"], h1["id"]]})
    assert [h["name"] for h in r.json()] == ["Main Auditorium", "Hall 4"]
    assert c.put(f"/api/events/{eid}/halls/order", headers=H(admin), json={"ids": [h1["id"]]}).status_code == 400
    assert c.patch(f"/api/events/{eid}/halls/{h1['id']}", headers=H(admin), json={"name": "Hall 5"}).json()["name"] == "Hall 5"
    h3 = c.post(f"/api/events/{eid}/halls", headers=H(admin), json={"name": "Temp"}).json()
    assert c.delete(f"/api/events/{eid}/halls/{h3['id']}", headers=H(admin)).status_code == 204

    # --- days: duplicate date, add, custom label, delete
    assert c.post(f"/api/events/{eid}/days", headers=H(admin), json={"day_date": "2027-02-08"}).status_code == 409
    d4 = c.post(f"/api/events/{eid}/days", headers=H(admin), json={"day_date": "2027-02-11", "label": "Gala Day"}).json()
    assert d4["label"] == "Gala Day"
    assert c.delete(f"/api/events/{eid}/days/{d4['id']}", headers=H(admin)).status_code == 204

    # --- a day / hall with sessions cannot be deleted
    day1 = c.get(f"/api/events/{eid}", headers=H(admin)).json()["days"][0]["id"]
    with SessionLocal() as db:
        db.add(m.Session(event_id=eid, day_id=day1, hall_id=h1["id"], title="Opening",
                         start_time=time(9), end_time=time(10)))
        db.commit()
    assert c.delete(f"/api/events/{eid}/days/{day1}", headers=H(admin)).status_code == 409
    assert c.delete(f"/api/events/{eid}/halls/{h1['id']}", headers=H(admin)).status_code == 409

    # --- invite an editor
    r = c.post(f"/api/events/{eid}/invitations", headers=H(admin), json={"email": "Ed@Example.com", "role": "editor"})
    assert r.status_code == 201
    inv = r.json()
    token = inv["link"].split("/invite/")[1]
    assert c.post(f"/api/events/{eid}/invitations", headers=H(admin), json={"email": "ed@example.com", "role": "viewer"}).status_code == 201
    assert len(c.get(f"/api/events/{eid}/invitations", headers=H(admin)).json()) == 1  # replaced, not duplicated
    token = c.get(f"/api/events/{eid}/invitations", headers=H(admin)).json()[0]["link"].split("/invite/")[1]
    prev = c.get(f"/api/auth/invite/{token}").json()
    assert prev["email"] == "ed@example.com" and prev["has_account"] is False
    assert c.post("/api/auth/accept-invite", json={"token": "nope", "password": "password1", "full_name": "E"}).status_code == 404
    editor = c.post("/api/auth/accept-invite", json={"token": token, "password": "password1", "full_name": "Ed"}).json()["access_token"]
    assert c.post("/api/auth/accept-invite", json={"token": token, "password": "password1", "full_name": "Ed"}).status_code == 404  # single-use

    # viewer role (the replacing invite) -> read only
    assert c.get(f"/api/events/{eid}", headers=H(editor)).json()["my_role"] == "viewer"
    assert c.patch(f"/api/events/{eid}", headers=H(editor), json={"name": "Hacked"}).status_code == 403
    assert c.post(f"/api/events/{eid}/halls", headers=H(editor), json={"name": "X"}).status_code == 403
    assert c.get(f"/api/events/{eid}/invitations", headers=H(editor)).status_code == 403
    assert c.get(f"/api/events/{eid}/members", headers=H(editor)).status_code == 200

    # --- admin changes role, notification toggles
    members = c.get(f"/api/events/{eid}/members", headers=H(admin)).json()
    ed = next(x for x in members if x["email"] == "ed@example.com")
    r = c.patch(f"/api/events/{eid}/members/{ed['id']}", headers=H(admin), json={"role": "editor", "receive_notifications": False})
    assert r.json()["role"] == "editor" and r.json()["receive_notifications"] is False
    assert c.get(f"/api/events/{eid}", headers=H(editor)).json()["my_role"] == "editor"
    assert c.patch(f"/api/events/{eid}", headers=H(editor), json={"name": "Hacked"}).status_code == 403  # editor can't change settings

    s = c.put(f"/api/events/{eid}/notification-settings", headers=H(admin), json={"type": "late_change", "enabled": False}).json()
    assert {x["type"]: x["enabled"] for x in s} == {"speaker_confirmed": True, "late_change": False}

    # last admin guard
    me = next(x for x in members if x["email"] == "a@example.com")
    assert c.patch(f"/api/events/{eid}/members/{me['id']}", headers=H(admin), json={"role": "viewer"}).status_code == 400
    assert c.delete(f"/api/events/{eid}/members/{me['id']}", headers=H(admin)).status_code == 400

    # --- multi-event isolation: editor's own event is invisible to admin and vice-versa
    other = c.post("/api/events", headers=H(editor), json={"name": "Editor's Own Event"}).json()["id"]
    assert c.get(f"/api/events/{other}", headers=H(admin)).status_code == 404
    assert c.get(f"/api/events/{other}/members", headers=H(admin)).status_code == 404
    assert len(c.get("/api/events", headers=H(editor)).json()) == 2
    assert len(c.get("/api/events", headers=H(admin)).json()) == 1

    # existing account accepting an invite to another event (password required)
    c.post(f"/api/events/{eid}/invitations", headers=H(editor), json={"email": "a@example.com"})  # editor not admin of eid
    r = c.post(f"/api/events/{other}/invitations", headers=H(editor), json={"email": "a@example.com", "role": "editor"})
    t2 = r.json()["link"].split("/invite/")[1]
    assert c.get(f"/api/auth/invite/{t2}").json()["has_account"] is True
    assert c.post("/api/auth/accept-invite", json={"token": t2, "password": "wrongpass1"}).status_code == 401
    assert c.post("/api/auth/accept-invite", json={"token": t2, "password": "password1"}).status_code == 200
    assert len(c.get("/api/events", headers=H(admin)).json()) == 2

    # --- archived = read-only (except switching status back)
    assert c.patch(f"/api/events/{eid}", headers=H(admin), json={"status": "archived"}).json()["status"] == "archived"
    assert c.post(f"/api/events/{eid}/halls", headers=H(admin), json={"name": "Late"}).status_code == 403
    assert c.patch(f"/api/events/{eid}", headers=H(admin), json={"name": "Renamed"}).status_code == 403
    assert c.patch(f"/api/events/{eid}", headers=H(admin), json={"status": "active"}).json()["status"] == "active"
    assert c.patch(f"/api/events/{eid}", headers=H(admin), json={"name": "Renamed"}).json()["name"] == "Renamed"

    # --- deleting an event removes everything attached (incl. sessions, speakers)
    with SessionLocal() as db:
        db.add(m.Speaker(event_id=eid, full_name="Dr. X"))
        db.commit()
    assert c.delete(f"/api/events/{eid}", headers=H(editor)).status_code == 403  # editor cannot delete
    assert c.delete(f"/api/events/{eid}", headers=H(admin)).status_code == 204
    with SessionLocal() as db:
        assert db.query(m.Session).filter_by(event_id=eid).count() == 0
        assert db.query(m.Speaker).filter_by(event_id=eid).count() == 0
        assert db.query(m.Hall).filter_by(event_id=eid).count() == 0
