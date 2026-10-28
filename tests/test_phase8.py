from conftest import H, make_user

FORM = {"full_name": "Dr. Meera Iyer", "designation": "Head of Packaging", "organisation": "GreenPack Ltd",
        "email": "meera@greenpack.com", "phone": "+91 98000 00000", "bio": "20 years in sustainable packaging.",
        "expertise": "Sustainable packaging, EPR", "topics": "Plastic waste rules and what they mean for brands",
        "proposed_title": "EPR in practice", "abstract": "A practical walk-through.", "formats": ["Panel Discussion", "Nope"],
        "availability": [], "requirements": "Laptop + clicker", "consent": True}


def _event(client, admin):
    ev = client.post("/api/events", headers=H(admin), json={"name": "Form Summit", "start_date": "2027-03-01", "end_date": "2027-03-02"}).json()
    eid = ev["id"]
    hall = client.post(f"/api/events/{eid}/halls", headers=H(admin), json={"name": "Hall 1"}).json()["id"]
    return eid, ev["days"][0]["id"], ev["days"][0]["label"], hall


def _invite(client, admin, eid, email="meera@greenpack.com"):
    r = client.post(f"/api/events/{eid}/speaker-invites", headers=H(admin),
                    json={"invitees": [{"name": "Meera", "email": email}], "message": "Hope you can join."})
    assert r.status_code == 201, r.text
    return r.json()["invites"][0]


def test_invite_form_review_and_assign(client, admin):
    eid, day, label, hall = _event(client, admin)
    inv = _invite(client, admin, eid)
    assert inv["link"].endswith("/#/speaker-form/" + inv["token"]) and not inv["submitted"]
    # inviting the same email again keeps the same link
    assert _invite(client, admin, eid)["token"] == inv["token"]

    info = client.get(f"/api/public/speaker-form/{inv['token']}")  # no auth header
    assert info.status_code == 200 and info.json()["status"] == "open" and info.json()["days"] == [label, info.json()["days"][1]]
    assert client.get("/api/public/speaker-form/nope").status_code == 404

    body = {**FORM, "availability": [label, "Made up day"]}
    assert client.post(f"/api/public/speaker-form/{inv['token']}", json={**body, "consent": False}).status_code == 422
    assert client.post(f"/api/public/speaker-form/{inv['token']}", json={**body, "hp": "bot"}).status_code == 201
    assert client.get(f"/api/events/{eid}/speaker-applications", headers=H(admin)).json() == []  # bot stored nothing
    assert client.post(f"/api/public/speaker-form/{inv['token']}", json=body).status_code == 201
    # speaker may correct the form while it is still pending
    assert client.post(f"/api/public/speaker-form/{inv['token']}", json={**body, "designation": "CEO"}).json()["updated"] is True

    apps = client.get(f"/api/events/{eid}/speaker-applications", headers=H(admin)).json()
    assert len(apps) == 1 and apps[0]["designation"] == "CEO" and apps[0]["formats"] == ["Panel Discussion"]
    assert apps[0]["availability"] == [label]
    assert client.get(f"/api/events/{eid}", headers=H(admin)).json()["counts"]["pending_applications"] == 1

    s = client.post(f"/api/events/{eid}/sessions", headers=H(admin), json={
        "day_id": day, "hall_id": hall, "title": "EPR Panel", "start_time": "10:00", "end_time": "11:00", "people": []}).json()
    aid = apps[0]["id"]
    r = client.post(f"/api/events/{eid}/speaker-applications/{aid}/approve", headers=H(admin),
                    json={"speaker_status": "Tentative", "session_id": s["id"], "role": "panelist"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "approved" and out["speaker_id"] and out["sessions"][0]["title"] == "EPR Panel"
    sp = client.get(f"/api/events/{eid}/speakers/{out['speaker_id']}", headers=H(admin)).json()
    assert sp["email"] == "meera@greenpack.com" and "EPR" in sp["internal_notes"] and sp["status"] == "Tentative"
    assert client.post(f"/api/events/{eid}/speaker-applications/{aid}/approve", headers=H(admin), json={}).status_code == 409
    assert client.post(f"/api/events/{eid}/speaker-applications/{aid}/reject", headers=H(admin), json={}).status_code == 409
    # reviewed: the speaker can no longer overwrite it
    assert client.post(f"/api/public/speaker-form/{inv['token']}", json=body).status_code == 409
    assert client.get(f"/api/public/speaker-form/{inv['token']}").json()["status"] == "approved"

    # unassign, then assign again through the plain endpoint
    r = client.delete(f"/api/events/{eid}/sessions/{s['id']}/people/{out['speaker_id']}", headers=H(admin))
    assert r.status_code == 200 and r.json()["people"] == []
    r = client.post(f"/api/events/{eid}/sessions/{s['id']}/people", headers=H(admin), json={"speaker_id": out["speaker_id"], "role": "moderator"})
    assert [p["role"] for p in r.json()["people"]] == ["moderator"]


def test_reject_restore_and_permissions(client, admin):
    eid, *_ = _event(client, admin)
    inv = _invite(client, admin, eid, "x@example.com")
    client.post(f"/api/public/speaker-form/{inv['token']}", json={**FORM, "email": "x@example.com"})
    aid = client.get(f"/api/events/{eid}/speaker-applications", headers=H(admin)).json()[0]["id"]

    viewer = make_user("viewer-sf@example.com")
    client.post(f"/api/events/{eid}/invitations", headers=H(admin), json={"email": "viewer-sf@example.com", "role": "viewer"})
    assert client.get(f"/api/events/{eid}/speaker-applications", headers=H(viewer)).status_code == 404  # not on the team

    r = client.post(f"/api/events/{eid}/speaker-applications/{aid}/reject", headers=H(admin), json={"note": "Topic not a fit"})
    assert r.json()["status"] == "rejected" and r.json()["review_note"] == "Topic not a fit"
    assert client.post(f"/api/events/{eid}/speaker-applications/{aid}/restore", headers=H(admin)).json()["status"] == "pending"
    assert client.get(f"/api/events/{eid}/speakers", headers=H(admin)).json() == []  # rejecting never adds a speaker

    # another event never sees this event's data
    other = make_user("other-sf@example.com")
    assert client.get(f"/api/events/{eid}/speaker-invites", headers=H(other)).status_code == 404
    assert client.delete(f"/api/events/{eid}/speaker-invites/{inv['id']}", headers=H(admin)).status_code == 204
    assert client.get(f"/api/public/speaker-form/{inv['token']}").status_code == 404  # link switched off
    assert len(client.get(f"/api/events/{eid}/speaker-applications", headers=H(admin)).json()) == 1  # response kept


def test_shared_invite_link(client, admin):
    eid, *_ = _event(client, admin)
    url = f"/api/events/{eid}/speaker-form-link"
    assert client.get(url, headers=H(admin)).json() == {"enabled": False, "token": None, "link": None}

    on = client.put(url, headers=H(admin), json={"enabled": True}).json()
    assert on["enabled"] and on["link"].endswith("/#/speaker-form/open/" + on["token"])
    assert client.put(url, headers=H(admin), json={"enabled": True}).json()["token"] == on["token"]  # same address

    pub = f"/api/public/speaker-form/open/{on['token']}"
    info = client.get(pub)  # no auth header
    assert info.status_code == 200 and info.json()["status"] == "open" and info.json()["invitee_email"] == ""
    body = {**FORM, "email": "walkin@example.com"}
    assert client.post(pub, json={**body, "consent": False}).status_code == 422
    assert client.post(pub, json={**body, "email": ""}).status_code == 422  # no personal invite, so an email is required
    assert client.post(pub, json={**body, "hp": "bot"}).status_code == 201
    assert client.get(f"/api/events/{eid}/speaker-applications", headers=H(admin)).json() == []
    assert client.post(pub, json=body).status_code == 201
    assert client.post(pub, json={**body, "designation": "Founder"}).json()["updated"] is True  # same email: no duplicate
    other = client.post(pub, json={**body, "email": "second@example.com", "full_name": "Second Person"})
    assert other.status_code == 201

    apps = client.get(f"/api/events/{eid}/speaker-applications", headers=H(admin)).json()
    assert len(apps) == 2 and not any(a["invited"] for a in apps)
    first = next(a for a in apps if a["email"] == "walkin@example.com")
    assert first["designation"] == "Founder"
    assert client.post(f"/api/events/{eid}/speaker-applications/{first['id']}/approve", headers=H(admin), json={}).status_code == 200
    assert client.post(pub, json=body).status_code == 409  # already reviewed

    # only an admin manages the link; a stranger cannot even see it
    assert client.get(url, headers=H(make_user("stranger-link@example.com"))).status_code == 404

    new = client.post(url + "/renew", headers=H(admin)).json()
    assert new["token"] != on["token"] and client.get(pub).status_code == 404  # old address is dead
    assert client.get(f"/api/public/speaker-form/open/{new['token']}").status_code == 200
    assert client.put(url, headers=H(admin), json={"enabled": False}).json()["enabled"] is False
    assert client.get(f"/api/public/speaker-form/open/{new['token']}").status_code == 404