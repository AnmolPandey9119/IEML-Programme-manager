from conftest import H, make_user


def _ids(client, admin, event):
    halls = {h["name"]: h["id"] for h in event["halls"]}
    days = [d["id"] for d in event["days"]]
    return halls, days


def _body(day, hall, start, end, title="Session", **kw):
    b = {"day_id": day, "hall_id": hall, "title": title, "start_time": start, "end_time": end}
    b.update(kw)
    return b


def _mk_speaker(client, admin, eid, name, status="Confirmed"):
    return client.post(f"/api/events/{eid}/speakers", headers=H(admin), json={"full_name": name, "status": status}).json()["id"]


def codes(ws):
    return sorted(w["code"] for w in ws)


def test_create_edit_and_fields(client, admin, event):
    eid = event["id"]; halls, days = _ids(client, admin, event); base = f"/api/events/{eid}/sessions"
    sp = _mk_speaker(client, admin, eid, "Dr. Rao"); mod = _mk_speaker(client, admin, eid, "Meera Iyer")
    r = client.post(base, headers=H(admin), json=_body(
        days[0], halls["Hall 4"], "10:00", "11:30", "Future of Green Hydrogen", session_type="Panel Discussion",
        writeup="  A discussion.  ", subtopics=["Cost curves", " ", "Policy support"], status="published", internal_notes="VIP row",
        people=[{"speaker_id": sp, "role": "panelist"}, {"speaker_id": mod, "role": "moderator"}]))
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["duration_minutes"] == 90 and s["hall_name"] == "Hall 4" and s["status"] == "published"
    assert s["subtopics"] == ["Cost curves", "Policy support"] and s["writeup"] == "A discussion."
    assert [p["role"] for p in s["people"]] == ["moderator", "panelist"] and s["warnings"] == []
    # edit: move to merged hall; hall is cleared
    b = _body(days[0], halls["Hall 5"], "10:00", "11:30", "Future of Green Hydrogen", is_merged=True, session_type="Plenary",
              people=[{"speaker_id": sp, "role": "panelist"}])
    s2 = client.put(f"{base}/{s['id']}", headers=H(admin), json=b).json()
    assert s2["is_merged"] and s2["hall_id"] is None and s2["hall_name"] == "All halls"
    # validation
    assert client.post(base, headers=H(admin), json=_body(days[0], None, "10:00", "11:00", "")).status_code == 422
    assert client.post(base, headers=H(admin), json=_body(9999, None, "10:00", "11:00")).status_code == 422
    assert client.post(base, headers=H(admin), json=_body(days[0], 9999, "10:00", "11:00")).status_code == 422
    assert client.post(base, headers=H(admin), json=_body(days[0], None, "10:00", "11:00", session_type="Custom")).status_code == 422
    assert client.post(base, headers=H(admin), json=_body(days[0], None, "10:00", "11:00", people=[{"speaker_id": 99999}])).status_code == 422
    ok = client.post(base, headers=H(admin), json=_body(days[0], None, "12:00", "12:30", session_type="Custom", custom_type_label="Cultural Programme"))
    assert ok.status_code == 201 and ok.json()["type_label"] == "Cultural Programme" and ok.json()["hall_name"] == ""
    # speaker's "Sessions (auto)" updates
    spk = client.get(f"/api/events/{eid}/speakers/{sp}", headers=H(admin)).json()
    assert [x["title"] for x in spk["sessions"]] == ["Future of Green Hydrogen"] and spk["sessions"][0]["role"] == "panelist"


def test_every_conflict_rule_warns_and_never_blocks(client, admin, event):
    eid = event["id"]; halls, days = _ids(client, admin, event); base = f"/api/events/{eid}/sessions"
    a = _mk_speaker(client, admin, eid, "Speaker A")
    first = client.post(base, headers=H(admin), json=_body(days[0], halls["Hall 4"], "11:00", "12:00", "First", people=[{"speaker_id": a}])).json()
    chk = lambda **kw: client.post(base + "/check", headers=H(admin), json=_body(**kw)).json()

    assert codes(chk(day=days[0], hall=halls["Hall 4"], start="11:30", end="13:00", title="Same hall")) == ["hall_overlap"]
    assert chk(day=days[0], hall=halls["Hall 5"], start="11:30", end="13:00", title="Parallel") == []  # parallel tracks are fine
    assert codes(chk(day=days[1], hall=halls["Hall 4"], start="11:30", end="13:00", title="Other day")) == []  # days independent
    assert codes(chk(day=days[0], hall=halls["Hall 5"], start="11:30", end="13:00", title="Clash",
                     people=[{"speaker_id": a, "role": "moderator"}])) == ["speaker_double_booked"]  # any role counts
    assert codes(chk(day=days[0], hall=None, start="10:30", end="11:30", title="Plenary", is_merged=True, session_type="Plenary")) == ["merged_conflict"]
    assert codes(chk(day=days[0], hall=halls["Hall 5"], start="15:00", end="14:00", title="Backwards")) == ["end_before_start"]
    assert codes(chk(day=days[0], hall=halls["Hall 5"], start="23:00", end="01:00", title="Night")) == ["past_midnight"]
    assert codes(chk(day=days[0], hall=halls["Hall 5"], start="16:00", end="16:03", title="Tiny")) == ["unusual_duration"]
    assert codes(chk(day=days[0], hall=halls["Hall 5"], start="08:00", end="13:00", title="Marathon")) == ["unusual_duration"]
    tight = chk(day=days[0], hall=halls["Hall 4"], start="12:02", end="13:00", title="Tight")
    assert codes(tight) == ["tight_turnaround"] and tight[0]["level"] == "notice"
    assert chk(day=days[0], hall=halls["Hall 4"], start="12:02", end="13:00", title="Tea", session_type="Break") == []
    assert chk(day=days[0], hall=halls["Hall 4"], start="12:00", end="13:00", title="Back to back")[0]["code"] == "tight_turnaround"
    # editing the session itself does not conflict with itself
    assert chk(id=first["id"], day=days[0], hall=halls["Hall 4"], start="11:00", end="12:00", title="First", people=[{"speaker_id": a}]) == []

    # saving is never blocked, and saved sessions carry their warnings in the list
    r = client.post(base, headers=H(admin), json=_body(days[0], halls["Hall 4"], "11:30", "13:00", "Same hall"))
    assert r.status_code == 201 and codes(r.json()["warnings"]) == ["hall_overlap"]
    listed = {s["title"]: s for s in client.get(base, headers=H(admin)).json()}
    assert codes(listed["First"]["warnings"]) == ["hall_overlap"]


def test_roles_isolation_duplicate_delete(client, admin, event):
    eid = event["id"]; halls, days = _ids(client, admin, event); base = f"/api/events/{eid}/sessions"
    s = client.post(base, headers=H(admin), json=_body(days[0], halls["Hall 4"], "09:00", "10:00", "Opening", status="published")).json()
    for role in ("editor", "viewer"):
        email = f"p3.{role}@example.com"
        inv = client.post(f"/api/events/{eid}/invitations", headers=H(admin), json={"email": email, "role": role}).json()
        client.post("/api/auth/accept-invite", json={"token": inv["link"].split("/invite/")[1], "password": "password1", "full_name": role})
    ed, vw = make_user("p3.editor@example.com"), make_user("p3.viewer@example.com")
    assert client.get(base, headers=H(vw)).status_code == 200
    assert client.post(base + "/check", headers=H(vw), json=_body(days[0], None, "09:00", "10:00")).status_code == 200
    assert client.post(base, headers=H(vw), json=_body(days[0], None, "09:00", "10:00")).status_code == 403
    assert client.put(f"{base}/{s['id']}", headers=H(ed), json=_body(days[0], halls["Hall 4"], "09:00", "10:30", "Opening")).status_code == 200
    assert client.delete(f"{base}/{s['id']}", headers=H(ed)).status_code == 403
    dup = client.post(f"{base}/{s['id']}/duplicate", headers=H(ed)).json()
    assert dup["title"] == "Opening (copy)" and dup["status"] == "draft" and dup["id"] != s["id"]
    # another account cannot see or touch it
    other = make_user("p3.other@example.com")
    assert client.get(base, headers=H(other)).status_code == 404
    assert client.get(f"{base}/{s['id']}", headers=H(other)).status_code == 404
    # day/hall in use cannot be deleted; sessions of another event cannot be used as targets
    assert client.delete(f"/api/events/{eid}/halls/{halls['Hall 4']}", headers=H(admin)).status_code == 409
    ev2 = client.post("/api/events", headers=H(other), json={"name": "E2", "start_date": "2027-03-01", "end_date": "2027-03-01"}).json()
    assert client.post(base, headers=H(admin), json=_body(ev2["days"][0]["id"], None, "09:00", "10:00")).status_code == 422
    assert client.delete(f"{base}/{s['id']}", headers=H(admin)).status_code == 204
    assert client.get(f"{base}/{s['id']}", headers=H(admin)).status_code == 404
    # archived events are read-only
    client.patch(f"/api/events/{eid}", headers=H(admin), json={"status": "archived"})
    assert client.post(base, headers=H(admin), json=_body(days[0], None, "09:00", "10:00")).status_code == 403
