import io

from PIL import Image

from conftest import H, make_user


def _png(w=1200, h=900, mode="RGB"):
    buf = io.BytesIO()
    Image.new(mode, (w, h), (30, 120, 200) if mode == "RGB" else (30, 120, 200, 0)).save(buf, "PNG")
    return buf.getvalue()


def test_speaker_crud_filters_and_roles(client, admin, event):
    eid = event["id"]
    base = f"/api/events/{eid}/speakers"
    r = client.post(base, headers=H(admin), json={
        "full_name": " Dr. Asha Rao ", "designation": "Managing Director", "organisation": "GreenGrid",
        "email": "Asha@GreenGrid.in", "linkedin_url": "linkedin.com/in/asha"})
    assert r.status_code == 201
    sp = r.json()
    assert sp["full_name"] == "Dr. Asha Rao" and sp["status"] == "Invited" and sp["email"] == "asha@greengrid.in"
    assert sp["linkedin_url"] == "https://linkedin.com/in/asha" and sp["sessions"] == []
    assert client.post(base, headers=H(admin), json={"full_name": ""}).status_code == 422
    assert client.post(base, headers=H(admin), json={"full_name": "X", "email": "nope"}).status_code == 422

    client.post(base, headers=H(admin), json={"full_name": "Ravi Menon", "organisation": "SolarOne", "status": "Confirmed"})
    assert [s["full_name"] for s in client.get(base, headers=H(admin)).json()] == ["Dr. Asha Rao", "Ravi Menon"]
    assert len(client.get(base + "?status=Confirmed", headers=H(admin)).json()) == 1
    assert [s["full_name"] for s in client.get(base + "?q=solar", headers=H(admin)).json()] == ["Ravi Menon"]

    r = client.patch(f"{base}/{sp['id']}", headers=H(admin),
                     json={"status": "Declined", "status_remark": "Clashing travel", "bio": "Short bio"})
    assert r.json()["status"] == "Declined" and r.json()["status_remark"] == "Clashing travel"

    # roles: viewer read-only, editor may edit but not delete, admin may delete
    ed, vw = make_user("p2.editor@example.com"), make_user("p2.viewer@example.com")
    for tok, role in ((ed, "editor"), (vw, "viewer")):
        inv = client.post(f"/api/events/{eid}/invitations", headers=H(admin),
                          json={"email": "p2." + role + "@example.com", "role": role}).json()
        client.post("/api/auth/accept-invite", json={"token": inv["link"].split("/invite/")[1], "password": "password1"})
    assert client.get(base, headers=H(vw)).status_code == 200
    assert client.post(base, headers=H(vw), json={"full_name": "Nope"}).status_code == 403
    assert client.patch(f"{base}/{sp['id']}", headers=H(ed), json={"designation": "CEO"}).status_code == 200
    assert client.delete(f"{base}/{sp['id']}", headers=H(ed)).status_code == 403
    assert client.delete(f"{base}/{sp['id']}", headers=H(admin)).status_code == 204
    assert client.get(f"{base}/{sp['id']}", headers=H(admin)).status_code == 404


def test_speakers_are_isolated_between_events(client, admin, event):
    other = make_user("p2.other@example.com")
    ev2 = client.post("/api/events", headers=H(other), json={"name": "Other Event"}).json()
    sp = client.post(f"/api/events/{event['id']}/speakers", headers=H(admin), json={"full_name": "Secret"}).json()
    assert client.get(f"/api/events/{event['id']}/speakers", headers=H(other)).status_code == 404
    assert client.get(f"/api/events/{ev2['id']}/speakers/{sp['id']}", headers=H(other)).status_code == 404
    assert client.get(f"/api/events/{ev2['id']}/speakers", headers=H(other)).json() == []


def test_photo_upload_resize_serve_remove(client, admin, event):
    base = f"/api/events/{event['id']}/speakers"
    sp = client.post(base, headers=H(admin), json={"full_name": "Photo Person"}).json()
    r = client.post(f"{base}/{sp['id']}/photo", headers=H(admin), files={"file": ("a.png", _png(), "image/png")})
    assert r.status_code == 200 and r.json()["photo_url"].startswith("/api/media/speaker/")
    url = r.json()["photo_url"]
    img = client.get(url)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    assert max(Image.open(io.BytesIO(img.content)).size) == 800  # downscaled
    assert client.get(url[:-3] + "abc").status_code == 404  # bad signature
    assert client.post(f"{base}/{sp['id']}/photo", headers=H(admin),
                       files={"file": ("a.txt", b"not an image", "text/plain")}).status_code == 415
    gif = io.BytesIO(); Image.new("RGB", (10, 10)).save(gif, "GIF")
    assert client.post(f"{base}/{sp['id']}/photo", headers=H(admin),
                       files={"file": ("a.gif", gif.getvalue(), "image/gif")}).status_code == 415
    # transparent PNG is accepted
    assert client.post(f"{base}/{sp['id']}/photo", headers=H(admin),
                       files={"file": ("t.png", _png(100, 100, "RGBA"), "image/png")}).status_code == 200
    r = client.delete(f"{base}/{sp['id']}/photo", headers=H(admin))
    assert r.json()["photo_url"] == "" and client.get(url).status_code == 404


def test_confirmation_email_goes_to_team(client, admin, event, monkeypatch):
    sent = []
    import app.notify as notify
    monkeypatch.setattr(notify, "send_email", lambda to, subj, body, html_body=None: sent.append((to, subj, body)) or True)
    eid = event["id"]
    base = f"/api/events/{eid}/speakers"
    client.post(f"/api/events/{eid}/invitations", headers=H(admin), json={"email": "mate@example.com", "role": "editor"})
    inv = client.get(f"/api/events/{eid}/invitations", headers=H(admin)).json()[0]
    client.post("/api/auth/accept-invite", json={"token": inv["link"].split("/invite/")[1], "password": "password1", "full_name": "Mate"})

    sp = client.post(base, headers=H(admin), json={"full_name": "Dr. Kiran", "designation": "Director", "organisation": "Acme"}).json()
    assert not sent
    r = client.patch(f"{base}/{sp['id']}", headers=H(admin), json={"status": "Confirmed"})
    assert r.json()["team_notified"] == 2 and len(sent) == 1
    to, subject, body = sent[0]
    assert sorted(to) == ["mate@example.com", "owner@example.com"] and "Dr. Kiran" in subject
    assert "Director" in body and "Acme" in body and "not assigned to a session" in body
    # no repeat when already Confirmed
    client.patch(f"{base}/{sp['id']}", headers=H(admin), json={"bio": "x"})
    assert len(sent) == 1
    # per-person off
    members = client.get(f"/api/events/{eid}/members", headers=H(admin)).json()
    mate = next(m for m in members if m["email"] == "mate@example.com")
    client.patch(f"/api/events/{eid}/members/{mate['id']}", headers=H(admin), json={"receive_notifications": False})
    sp2 = client.post(base, headers=H(admin), json={"full_name": "Second", "status": "Confirmed"}).json()
    assert sent[-1][0] == ["owner@example.com"] and sp2["team_notified"] == 1
    # per-type off
    client.put(f"/api/events/{eid}/notification-settings", headers=H(admin), json={"type": "speaker_confirmed", "enabled": False})
    n = len(sent)
    sp3 = client.post(base, headers=H(admin), json={"full_name": "Third"}).json()
    client.patch(f"{base}/{sp3['id']}", headers=H(admin), json={"status": "Confirmed"})
    assert len(sent) == n
