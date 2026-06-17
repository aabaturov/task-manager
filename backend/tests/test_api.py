"""Automated API tests for SPEC-001 (and v1.0 regression)."""


def _project(client, name, **kw):
    r = client.post("/api/projects", json={"name": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def _task(client, project_id, text):
    r = client.post("/api/tasks", json={"project_id": project_id, "text": text})
    assert r.status_code == 201, r.text
    return r.json()


# --------------------------------------------------------------- v1.0 base
def test_requires_auth():
    from app.main import app
    from fastapi.testclient import TestClient

    anon = TestClient(app)
    assert anon.get("/api/projects").status_code == 401


def test_project_crud_and_duplicate(client):
    p = _project(client, "Inbox")
    assert p["type"] == "local"
    assert p["icon"] is None
    assert p["pinned"] is False
    # duplicate name
    assert client.post("/api/projects", json={"name": "Inbox"}).status_code == 409


# ----------------------------------------------- Feature 1: project icons
def test_create_project_with_icon_and_type(client):
    p = _project(client, "Work", icon="💼", type="global")
    assert p["icon"] == "💼"
    assert p["type"] == "global"


def test_patch_icon_set_and_clear(client):
    p = _project(client, "Home")
    r = client.patch(f"/api/projects/{p['id']}", json={"icon": "🏠"})
    assert r.status_code == 200 and r.json()["icon"] == "🏠"
    # clear with empty string
    r = client.patch(f"/api/projects/{p['id']}", json={"icon": ""})
    assert r.status_code == 200 and r.json()["icon"] is None


def test_patch_name_conflict(client):
    _project(client, "A")
    b = _project(client, "B")
    assert client.patch(f"/api/projects/{b['id']}", json={"name": "A"}).status_code == 409


# ------------------------------------------------ Feature 6: type & pinning
def test_pin_limit_three(client):
    ps = [_project(client, f"P{i}") for i in range(4)]
    for p in ps[:3]:
        r = client.patch(f"/api/projects/{p['id']}", json={"pinned": True})
        assert r.status_code == 200 and r.json()["pinned"] is True
    # 4th pin rejected
    r = client.patch(f"/api/projects/{ps[3]['id']}", json={"pinned": True})
    assert r.status_code == 409
    # unpin one, then 4th can be pinned
    assert client.patch(f"/api/projects/{ps[0]['id']}", json={"pinned": False}).status_code == 200
    assert client.patch(f"/api/projects/{ps[3]['id']}", json={"pinned": True}).status_code == 200


def test_pin_keeps_type(client):
    p = _project(client, "Glob", type="global")
    client.patch(f"/api/projects/{p['id']}", json={"pinned": True})
    r = client.patch(f"/api/projects/{p['id']}", json={"pinned": False})
    assert r.json()["type"] == "global"  # type preserved across pin/unpin


# ------------------------------------------------ Feature 5: ordering
def test_task_position_increments(client):
    p = _project(client, "Proj")
    t1 = _task(client, p["id"], "one")
    t2 = _task(client, p["id"], "two")
    t3 = _task(client, p["id"], "three")
    assert [t1["position"], t2["position"], t3["position"]] == [0, 1, 2]


def test_reorder(client):
    p = _project(client, "Proj")
    a = _task(client, p["id"], "a")
    b = _task(client, p["id"], "b")
    c = _task(client, p["id"], "c")
    r = client.post(
        f"/api/projects/{p['id']}/reorder",
        json={"task_ids": [c["id"], a["id"], b["id"]]},
    )
    assert r.status_code == 200
    order = [t["id"] for t in r.json()]
    assert order == [c["id"], a["id"], b["id"]]


def test_reorder_rejects_foreign_task(client):
    p1 = _project(client, "P1")
    p2 = _project(client, "P2")
    foreign = _task(client, p2["id"], "x")
    assert client.post(
        f"/api/projects/{p1['id']}/reorder", json={"task_ids": [foreign["id"]]}
    ).status_code == 400


def test_reorder_partial_keeps_others_at_end(client):
    p = _project(client, "Proj")
    a = _task(client, p["id"], "a")
    b = _task(client, p["id"], "b")
    c = _task(client, p["id"], "c")
    # only mention c first; a,b keep relative order after
    r = client.post(
        f"/api/projects/{p['id']}/reorder", json={"task_ids": [c["id"]]}
    )
    order = [t["id"] for t in r.json()]
    assert order == [c["id"], a["id"], b["id"]]


# --------------------------- Features 2/3/4: edit, important, deadline, done
def test_edit_task_text(client):
    p = _project(client, "Proj")
    t = _task(client, p["id"], "old")
    r = client.patch(f"/api/tasks/{t['id']}", json={"text": "  new  "})
    assert r.status_code == 200 and r.json()["text"] == "new"  # trimmed


def test_edit_empty_text_rejected(client):
    p = _project(client, "Proj")
    t = _task(client, p["id"], "keep")
    assert client.patch(f"/api/tasks/{t['id']}", json={"text": "   "}).status_code == 422
    # original unchanged
    tasks = client.get("/api/tasks").json()
    assert tasks[0]["text"] == "keep"


def test_edit_missing_task(client):
    assert client.patch("/api/tasks/99999", json={"text": "x"}).status_code == 404


def test_important_and_deadline(client):
    p = _project(client, "Proj")
    t = _task(client, p["id"], "task")
    r = client.patch(
        f"/api/tasks/{t['id']}", json={"important": True, "deadline": "2020-01-01"}
    )
    body = r.json()
    assert body["important"] is True and body["deadline"] == "2020-01-01"
    # clear deadline
    r = client.patch(f"/api/tasks/{t['id']}", json={"deadline": None})
    assert r.json()["deadline"] is None


def test_done_toggle_preserves_on_edit(client):
    p = _project(client, "Proj")
    t = _task(client, p["id"], "task")
    client.patch(f"/api/tasks/{t['id']}", json={"done": True})
    # editing text keeps done status
    r = client.patch(f"/api/tasks/{t['id']}", json={"text": "renamed"})
    assert r.json()["done"] is True and r.json()["text"] == "renamed"


# ------------------------------------------- Feature 8: day slots
def test_day_slots_default_three_empty(client):
    slots = client.get("/api/day-slots").json()
    assert [s["index"] for s in slots] == [0, 1, 2]
    assert all(s["task_ids"] == [] for s in slots)


def test_day_slot_set_and_move(client):
    p = _project(client, "Proj")
    a = _task(client, p["id"], "a")
    b = _task(client, p["id"], "b")
    # put a,b in slot 0
    client.put("/api/day-slots/0", json={"task_ids": [a["id"], b["id"]]})
    slots = client.get("/api/day-slots").json()
    assert slots[0]["task_ids"] == [a["id"], b["id"]]
    # selecting a in slot 1 moves it out of slot 0 (one slot max)
    client.put("/api/day-slots/1", json={"task_ids": [a["id"]]})
    slots = client.get("/api/day-slots").json()
    assert slots[0]["task_ids"] == [b["id"]]
    assert slots[1]["task_ids"] == [a["id"]]


def test_day_slot_dedup_and_missing_task(client):
    p = _project(client, "Proj")
    a = _task(client, p["id"], "a")
    client.put("/api/day-slots/0", json={"task_ids": [a["id"], a["id"]]})
    assert client.get("/api/day-slots").json()[0]["task_ids"] == [a["id"]]
    assert client.put("/api/day-slots/0", json={"task_ids": [99999]}).status_code == 404


def test_deleting_task_removes_from_slot(client):
    p = _project(client, "Proj")
    a = _task(client, p["id"], "a")
    client.put("/api/day-slots/0", json={"task_ids": [a["id"]]})
    client.delete(f"/api/tasks/{a['id']}")
    assert client.get("/api/day-slots").json()[0]["task_ids"] == []


def test_invalid_slot_index(client):
    assert client.put("/api/day-slots/5", json={"task_ids": []}).status_code == 404


def test_delete_project_cascades_tasks_and_slots(client):
    p = _project(client, "Proj")
    a = _task(client, p["id"], "a")
    client.put("/api/day-slots/0", json={"task_ids": [a["id"]]})
    client.delete(f"/api/projects/{p['id']}")
    assert client.get("/api/tasks").json() == []
    assert client.get("/api/day-slots").json()[0]["task_ids"] == []
