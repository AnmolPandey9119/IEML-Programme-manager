from datetime import timedelta

from conftest import H, make_user
from app.timeutil import local_now


def _setup(client, admin, start, end="", name="Live Event"):
    ev = client.post("/api/events", headers=H(admin), json={"name": name, "venue_name": "Expo Mart", "start_date": start, "end_date": end or start}).json()
    eid = ev["id"]
    hall = client.post(f"/api/events/{eid}/halls", headers=H(admin), json={"name": "Hall 4"}).json()["id"]
    hall2 = client.post(f"/api/events/{eid}/halls", headers=H(admin), json={"name": "Hall 5"}).json()["id"]
    return ev, eid, ev["days"][0]["id"], hall, hall2


def _sp(client, admin, eid, name, status):
    return client.post(f"/api/events/{eid}/speakers", headers=H(admin), json={
        "full_name": name, "status": status, "email": "secret@example.com", "phone": "999", "internal_notes": "private", "bio": "Bio of " + name}).json()["id"]


def _session(client, admin, eid, day, hall, title, status="published", merged=False, people=(), start="10:00", end="11:00"):
    r = client.post(f"/api/events/{eid}/sessions", headers=H(admin), json={
        "day_id": day, "hall_id": hall, "is_merged": merged, "title": title, "start_time": start, "end_time": end, "status": status,
        "internal_notes": "INTERNAL", "writeup": "About " + title, "subtopics": ["Point one"],
        "people": [{"speaker_id": i, "role": r} for i, r in people]})
    assert r.status_code == 201, r.text
    return r.json()


def test_public_agenda_rules(client, admin):
    ev, eid, day, hall, hall2 = _setup(client, admin, "2027-05-10")
    key = ev["public_key"]; url = f"/api/public/events/{key}/agenda"
    assert client.get("/api/public/events/unknown/agenda").status_code == 404
    assert client.get(url).status_code == 404  # Draft events are team-only
    a, b = _sp(client, admin, eid, "Confirmed One", "Confirmed"), _sp(client, admin, eid, "Tentative Two", "Tentative")
    _session(client, admin, eid, day, hall, "Public Panel", people=[(a, "panelist"), (b, "panelist")])
    _session(client, admin, eid, day, hall2, "Hidden Draft", status="draft")
    _session(client, admin, eid, day, None, "Opening Plenary", merged=True, start="09:00", end="09:45")
    client.patch(f"/api/events/{eid}", headers=H(admin), json={"status": "active"})

    r = client.get(url)  # no auth header at all
    assert r.status_code == 200 and "max-age=5" in r.headers["cache-control"]
    data = r.json(); titles = [s["title"] for s in data["days"][0]["sessions"]]
    assert titles == ["Opening Plenary", "Public Panel"]  # draft is excluded, sorted by time
    plenary, panel = data["days"][0]["sessions"]
    assert plenary["hall"] == "Expo Mart" and plenary["is_merged"] is True  # merged shows the venue name
    assert [p["name"] for p in panel["speakers"]] == ["Confirmed One"]  # unconfirmed speaker hidden
    assert panel["start_label"] == "10:00 AM" and panel["subtopics"] == ["Point one"]
    raw = r.text
    for secret in ("secret@example.com", "INTERNAL", "private", "999", "Tentative Two", "Hidden Draft"):
        assert secret not in raw
    # filters
    assert [s["title"] for s in client.get(url + f"?hall={hall2}").json()["days"][0]["sessions"]] == ["Opening Plenary"]
    # ETag => 304
    et = r.headers["etag"]
    assert client.get(url, headers={"If-None-Match": et}).status_code == 304
    # CORS is open for GET only
    cors = client.get(url, headers={"Origin": "https://sponsor.example"})
    assert cors.headers["access-control-allow-origin"] == "*"
    # any change shows up on the very next request (well inside 30 seconds)
    client.patch(f"/api/events/{eid}/speakers/{b}", headers=H(admin), json={"status": "Confirmed"})
    panel = client.get(url).json()["days"][0]["sessions"][1]
    assert [p["name"] for p in panel["speakers"]] == ["Confirmed One", "Tentative Two"]
    assert client.get(url, headers={"If-None-Match": et}).status_code == 200  # etag changed
    # archived stays readable; back to draft hides it again
    client.patch(f"/api/events/{eid}", headers=H(admin), json={"status": "archived"})
    assert client.get(url).status_code == 200
    client.patch(f"/api/events/{eid}", headers=H(admin), json={"status": "draft"})
    assert client.get(url).status_code == 404


def test_embed_script_is_served(client):
    r = client.get("/embed.js")
    assert r.status_code == 200 and "attachShadow" in r.text


def test_late_change_alert(client, admin, monkeypatch):
    sent = []
    import app.notify as notify
    monkeypatch.setattr(notify, "send_email", lambda to, subj, body, html_body=None: sent.append((to, subj, body)) or True)
    tomorrow = (local_now().date() + timedelta(days=1)).isoformat()
    far = (local_now().date() + timedelta(days=40)).isoformat()

    ev, eid, day, hall, hall2 = _setup(client, admin, tomorrow, name="Soon Event")
    who = _sp(client, admin, eid, "Dr. Late", "Confirmed")
    s = _session(client, admin, eid, day, hall, "Tomorrow Panel")
    put = lambda **kw: client.put(f"/api/events/{eid}/sessions/{s['id']}", headers=H(admin), json={
        "day_id": day, "hall_id": kw.get("hall", hall), "title": kw.get("title", "Tomorrow Panel"), "start_time": kw.get("start", "10:00"),
        "end_time": kw.get("end", "11:00"), "status": kw.get("status", "published"), "people": kw.get("people", [])})
    n = len(sent)
    assert put(title="Tomorrow Panel (renamed)").status_code == 200 and len(sent) == n  # title is not a time/hall/speaker change
    put(start="10:30", end="11:30")
    assert len(sent) == n + 1 and "Late change" in sent[-1][1] and "10:00 AM to 11:00 AM changed to 10:30 AM to 11:30 AM" in sent[-1][2]
    assert put(start="10:30", end="11:30", hall=hall2).status_code == 200
    assert "Hall: Hall 4 changed to Hall 5" in sent[-1][2]
    put(start="10:30", end="11:30", hall=hall2, people=[{"speaker_id": who, "role": "speaker"}])
    assert "Speakers added: Dr. Late" in sent[-1][2]
    count = len(sent)
    put(start="10:30", end="11:30", hall=hall2, people=[{"speaker_id": who, "role": "speaker"}], status="draft")  # unpublishing alone: no alert
    assert len(sent) == count

    # far-away event day: no alert. Admin can switch the alert off.
    ev2, eid2, day2, hall2a, _ = _setup(client, admin, far, name="Far Event")
    s2 = _session(client, admin, eid2, day2, hall2a, "Later")
    client.put(f"/api/events/{eid2}/sessions/{s2['id']}", headers=H(admin), json={"day_id": day2, "hall_id": hall2a, "title": "Later", "start_time": "12:00", "end_time": "13:00", "status": "published"})
    assert len(sent) == count
    client.put(f"/api/events/{eid}/notification-settings", headers=H(admin), json={"type": "late_change", "enabled": False})
    put(start="14:00", end="15:00", hall=hall2, status="published")
    assert len(sent) == count
