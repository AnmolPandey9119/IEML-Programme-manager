from conftest import H, make_user


def test_groups_members_meetings_flow(client, admin, event):
    eid = event["id"]; base = f"/api/events/{eid}"
    g = client.post(f"{base}/groups", headers=H(admin), json={"name": "Organising Committee", "group_type": "OC"}).json()
    assert g["group_type"] == "OC" and g["members"] == [] and g["share"]["enabled"] is False
    gid = g["id"]
    # members: add, reorder, edit, remove
    for n, role in (("Dr. Sunita Verma", "Chair"), ("Rohit Gupta", "Member"), ("Neha Singh", "Secretary")):
        r = client.post(f"{base}/groups/{gid}/members", headers=H(admin), json={"name": n, "role_in_group": role, "email": f"{n.split()[-1].lower()}@example.com"})
        assert r.status_code == 201
    det = r.json(); ids = [m["id"] for m in det["members"]]
    assert [m["name"] for m in det["members"]][0] == "Dr. Sunita Verma"
    r = client.put(f"{base}/groups/{gid}/members/order", headers=H(admin), json={"ids": [ids[2], ids[0], ids[1]]})
    assert [m["name"] for m in r.json()["members"]] == ["Neha Singh", "Dr. Sunita Verma", "Rohit Gupta"]
    assert client.put(f"{base}/groups/{gid}/members/order", headers=H(admin), json={"ids": ids[:2]}).status_code == 400
    r = client.patch(f"{base}/groups/{gid}/members/{ids[1]}", headers=H(admin), json={"name": "Rohit Gupta", "role_in_group": "Treasurer", "phone": "99999"})
    assert next(m for m in r.json()["members"] if m["id"] == ids[1])["role_in_group"] == "Treasurer"
    assert client.post(f"{base}/groups/{gid}/members", headers=H(admin), json={"name": ""}).status_code == 422

    # same person in another group with a different role + suggestions
    g2 = client.post(f"{base}/groups", headers=H(admin), json={"name": "Advisory Council", "group_type": "Advisory Council"}).json()
    client.post(f"{base}/groups/{g2['id']}/members", headers=H(admin), json={"name": "Rohit Gupta", "role_in_group": "Advisor"})
    sug = client.get(f"{base}/people?q=rohit", headers=H(admin)).json()
    assert sug and sug[0]["name"] == "Rohit Gupta"

    # meetings + attendance + minutes
    r = client.post(f"{base}/groups/{gid}/meetings", headers=H(admin), json={
        "title": "Kick-off", "meeting_date": "2027-01-10", "start_time": "15:00", "duration_minutes": 90,
        "location": "Conference Room 2, Expo Mart", "agenda": "- Budget\n- Venue"})
    assert r.status_code == 201
    mt = r.json()["meetings"][0]
    assert mt["end_time"] == "16:30:00" and mt["status"] == "Scheduled" and all(a["status"] == "unmarked" for a in mt["attendance"])
    marks = {str(ids[0]): "attended", str(ids[1]): "apologies", str(ids[2]): "absent"}
    r = client.put(f"{base}/groups/{gid}/meetings/{mt['id']}/attendance", headers=H(admin), json={"marks": marks})
    assert sorted(a["status"] for a in r.json()["meetings"][0]["attendance"]) == ["absent", "apologies", "attended"]
    assert client.put(f"{base}/groups/{gid}/meetings/{mt['id']}/attendance", headers=H(admin), json={"marks": {"99999": "attended"}}).status_code == 422
    r = client.patch(f"{base}/groups/{gid}/meetings/{mt['id']}", headers=H(admin), json={
        "title": "Kick-off", "meeting_date": "2027-01-10", "start_time": "15:00", "duration_minutes": 90, "location": "Room 2",
        "agenda": "x", "minutes": "Budget approved.", "status": "Completed"})
    m2 = r.json()["meetings"][0]
    assert m2["status"] == "Completed" and m2["minutes"] == "Budget approved." and m2["location"] == "Room 2"
    assert sorted(a["status"] for a in m2["attendance"]) == ["absent", "apologies", "attended"]  # attendance survives edits
    assert client.post(f"{base}/groups/{gid}/meetings", headers=H(admin), json={"title": "x", "meeting_date": "2027-01-10", "duration_minutes": 1}).status_code == 422

    # archive = read-only and hidden from the main list
    assert len(client.get(f"{base}/groups", headers=H(admin)).json()) == 2
    client.patch(f"{base}/groups/{g2['id']}", headers=H(admin), json={"archived": True})
    assert [x["name"] for x in client.get(f"{base}/groups", headers=H(admin)).json()] == ["Organising Committee"]
    assert [x["name"] for x in client.get(f"{base}/groups?archived=true", headers=H(admin)).json()] == ["Advisory Council"]
    assert client.post(f"{base}/groups/{g2['id']}/members", headers=H(admin), json={"name": "Late"}).status_code == 403
    assert client.patch(f"{base}/groups/{g2['id']}", headers=H(admin), json={"name": "Renamed"}).status_code == 403
    assert client.patch(f"{base}/groups/{g2['id']}", headers=H(admin), json={"archived": False}).status_code == 200


def test_share_link_roles_isolation(client, admin, event):
    eid = event["id"]; base = f"/api/events/{eid}"
    gid = client.post(f"{base}/groups", headers=H(admin), json={"name": "Advisory Council", "group_type": "Advisory Council"}).json()["id"]
    client.post(f"{base}/groups/{gid}/members", headers=H(admin), json={
        "name": "Prof. Iyer", "designation": "Dean", "organisation": "IIT", "email": "iyer@example.com", "phone": "12345", "notes": "private", "role_in_group": "Chair"})
    assert client.get("/api/public/groups/nope").status_code == 404
    s = client.put(f"{base}/groups/{gid}/share", headers=H(admin), json={"enabled": True, "include_contacts": False}).json()
    tok = s["token"]
    pub = client.get(f"/api/public/groups/{tok}")  # no auth header
    assert pub.status_code == 200
    m = pub.json()["members"][0]
    assert m["name"] == "Prof. Iyer" and m["role_in_group"] == "Chair" and "email" not in m and "phone" not in m and "notes" not in m
    client.put(f"{base}/groups/{gid}/share", headers=H(admin), json={"enabled": True, "include_contacts": True})
    assert client.get(f"/api/public/groups/{tok}").json()["members"][0]["email"] == "iyer@example.com"
    new = client.post(f"{base}/groups/{gid}/share/renew", headers=H(admin)).json()["token"]
    assert new != tok and client.get(f"/api/public/groups/{tok}").status_code == 404 and client.get(f"/api/public/groups/{new}").status_code == 200
    client.put(f"{base}/groups/{gid}/share", headers=H(admin), json={"enabled": False})
    assert client.get(f"/api/public/groups/{new}").status_code == 404

    # roles
    for role in ("editor", "viewer"):
        inv = client.post(f"{base}/invitations", headers=H(admin), json={"email": f"p4.{role}@example.com", "role": role}).json()
        client.post("/api/auth/accept-invite", json={"token": inv["link"].split("/invite/")[1], "password": "password1", "full_name": role})
    ed, vw = make_user("p4.editor@example.com"), make_user("p4.viewer@example.com")
    assert client.get(f"{base}/groups/{gid}", headers=H(vw)).status_code == 200
    assert client.get(f"{base}/groups/{gid}", headers=H(vw)).json()["share"]["token"] is None  # token only for admins
    assert client.post(f"{base}/groups/{gid}/members", headers=H(vw), json={"name": "X"}).status_code == 403
    assert client.post(f"{base}/groups/{gid}/members", headers=H(ed), json={"name": "Y"}).status_code == 201
    assert client.put(f"{base}/groups/{gid}/share", headers=H(ed), json={"enabled": True}).status_code == 403
    assert client.delete(f"{base}/groups/{gid}", headers=H(ed)).status_code == 403
    # isolation
    other = make_user("p4.other@example.com")
    assert client.get(f"{base}/groups", headers=H(other)).status_code == 404
    ev2 = client.post("/api/events", headers=H(other), json={"name": "E2"}).json()["id"]
    assert client.get(f"/api/events/{ev2}/groups/{gid}", headers=H(other)).status_code == 404
    assert client.delete(f"{base}/groups/{gid}", headers=H(admin)).status_code == 204
