"""API tests for SPEC-004 (file SPEC-004.md, header says SPEC-002).

Covers the new server logic:
  * Feature 2: light tasks ("не забыть") CRUD + trimming/empty rules.
  * Feature 3: calendar events — standalone events, project-task binding,
    date != deadline, time mandatory, deletion/unbinding leaves calendar.
  * Feature 1: project type rename ("temporary"/"permanent", default temporary).
"""


def _project(client, name, **kw):
    r = client.post("/api/projects", json={"name": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def _task(client, project_id, text):
    r = client.post("/api/tasks", json={"project_id": project_id, "text": text})
    assert r.status_code == 201, r.text
    return r.json()


# --------------------------------------------------- Feature 1: project types
def test_project_default_type_is_temporary(client):
    p = _project(client, "Inbox")
    assert p["type"] == "temporary"


def test_project_type_permanent(client):
    p = _project(client, "Sport", type="permanent")
    assert p["type"] == "permanent"


def test_old_type_values_rejected(client):
    # "local"/"global" are no longer valid input values (renamed).
    assert client.post(
        "/api/projects", json={"name": "X", "type": "local"}
    ).status_code == 422
    assert client.post(
        "/api/projects", json={"name": "Y", "type": "global"}
    ).status_code == 422


def test_change_type_between_groups(client):
    p = _project(client, "Proj", type="temporary")
    r = client.patch(f"/api/projects/{p['id']}", json={"type": "permanent"})
    assert r.status_code == 200 and r.json()["type"] == "permanent"


# ------------------------------------------------------ Feature 2: light tasks
def test_light_task_add_list_order(client):
    a = client.post("/api/light-tasks", json={"text": "buy milk"})
    b = client.post("/api/light-tasks", json={"text": "call mom"})
    assert a.status_code == 201 and b.status_code == 201
    items = client.get("/api/light-tasks").json()
    assert [i["text"] for i in items] == ["buy milk", "call mom"]  # add order
    assert all(i["done"] is False for i in items)


def test_light_task_trims_text(client):
    r = client.post("/api/light-tasks", json={"text": "   spaced   "})
    assert r.status_code == 201 and r.json()["text"] == "spaced"


def test_light_task_empty_rejected(client):
    # Pydantic min_length=1 catches "", server trim catches whitespace-only.
    assert client.post("/api/light-tasks", json={"text": ""}).status_code == 422
    assert client.post("/api/light-tasks", json={"text": "   "}).status_code == 422
    assert client.get("/api/light-tasks").json() == []


def test_light_task_mark_done_keeps_in_list(client):
    r = client.post("/api/light-tasks", json={"text": "x"})
    lid = r.json()["id"]
    upd = client.patch(f"/api/light-tasks/{lid}", json={"done": True})
    assert upd.status_code == 200 and upd.json()["done"] is True
    # still present
    items = client.get("/api/light-tasks").json()
    assert len(items) == 1 and items[0]["done"] is True


def test_light_task_delete(client):
    r = client.post("/api/light-tasks", json={"text": "x"})
    lid = r.json()["id"]
    assert client.delete(f"/api/light-tasks/{lid}").status_code == 204
    assert client.get("/api/light-tasks").json() == []


def test_light_task_missing(client):
    assert client.patch("/api/light-tasks/999", json={"done": True}).status_code == 404
    assert client.delete("/api/light-tasks/999").status_code == 404


def test_light_tasks_independent_from_project_tasks(client):
    p = _project(client, "Proj")
    _task(client, p["id"], "project task")
    client.post("/api/light-tasks", json={"text": "light"})
    # Light tasks do not appear among project tasks and vice versa.
    assert [t["text"] for t in client.get("/api/tasks").json()] == ["project task"]
    assert [i["text"] for i in client.get("/api/light-tasks").json()] == ["light"]


# ------------------------------------------------ Feature 3: calendar events
def test_create_standalone_event(client):
    r = client.post(
        "/api/events",
        json={"text": "Dentist", "event_date": "2026-07-01", "event_time": "09:30"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["project_id"] is None
    assert body["text"] == "Dentist"
    assert body["event_date"] == "2026-07-01"
    assert body["event_time"] == "09:30:00"
    assert body["done"] is False


def test_event_time_required(client):
    # Missing time is rejected at the schema level.
    assert client.post(
        "/api/events", json={"text": "x", "event_date": "2026-07-01"}
    ).status_code == 422


def test_standalone_event_not_on_board(client):
    client.post(
        "/api/events",
        json={"text": "solo", "event_date": "2026-07-01", "event_time": "10:00"},
    )
    # /api/tasks lists every task incl. standalone, but it has no project_id,
    # so it never renders on the board; events endpoint is the calendar source.
    events = client.get("/api/events").json()
    assert [e["text"] for e in events] == ["solo"]
    board_tasks = [t for t in client.get("/api/tasks").json() if t["project_id"]]
    assert board_tasks == []


def test_events_range_filter(client):
    for d in ("2026-06-30", "2026-07-15", "2026-08-01"):
        client.post(
            "/api/events",
            json={"text": d, "event_date": d, "event_time": "12:00"},
        )
    r = client.get("/api/events", params={"start": "2026-07-01", "end": "2026-07-31"})
    assert [e["event_date"] for e in r.json()] == ["2026-07-15"]


def test_events_sorted_by_date_then_time(client):
    client.post("/api/events", json={"text": "b", "event_date": "2026-07-01", "event_time": "15:00"})
    client.post("/api/events", json={"text": "a", "event_date": "2026-07-01", "event_time": "08:00"})
    client.post("/api/events", json={"text": "c", "event_date": "2026-06-30", "event_time": "23:00"})
    texts = [e["text"] for e in client.get("/api/events").json()]
    assert texts == ["c", "a", "b"]


def test_edit_standalone_event(client):
    e = client.post(
        "/api/events",
        json={"text": "old", "event_date": "2026-07-01", "event_time": "10:00"},
    ).json()
    r = client.patch(f"/api/events/{e['id']}", json={"text": "  new  ", "done": True})
    assert r.status_code == 200
    assert r.json()["text"] == "new" and r.json()["done"] is True


def test_event_time_cannot_be_cleared(client):
    e = client.post(
        "/api/events",
        json={"text": "x", "event_date": "2026-07-01", "event_time": "10:00"},
    ).json()
    assert client.patch(
        f"/api/events/{e['id']}", json={"event_time": None}
    ).status_code == 422


def test_delete_standalone_event(client):
    e = client.post(
        "/api/events",
        json={"text": "x", "event_date": "2026-07-01", "event_time": "10:00"},
    ).json()
    assert client.delete(f"/api/events/{e['id']}").status_code == 204
    assert client.get("/api/events").json() == []


def test_past_event_stays(client):
    client.post(
        "/api/events",
        json={"text": "past", "event_date": "2020-01-01", "event_time": "09:00"},
    )
    events = client.get("/api/events").json()
    assert [e["text"] for e in events] == ["past"]


# ----------------------------- project-task date binding (event from a task)
def test_bind_project_task_to_date_makes_event(client):
    p = _project(client, "Proj")
    t = _task(client, p["id"], "task")
    r = client.put(
        f"/api/tasks/{t['id']}/event",
        json={"event_date": "2026-07-04", "event_time": "18:00"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["event_date"] == "2026-07-04"
    assert body["event_time"] == "18:00:00"
    # Now appears in the calendar, still linked to the project.
    events = client.get("/api/events").json()
    assert len(events) == 1 and events[0]["project_id"] == p["id"]


def test_unbind_project_task_leaves_calendar_keeps_task(client):
    p = _project(client, "Proj")
    t = _task(client, p["id"], "task")
    client.put(
        f"/api/tasks/{t['id']}/event",
        json={"event_date": "2026-07-04", "event_time": "18:00"},
    )
    # Clear binding (both null).
    r = client.put(
        f"/api/tasks/{t['id']}/event", json={"event_date": None, "event_time": None}
    )
    assert r.status_code == 200 and r.json()["event_date"] is None
    assert client.get("/api/events").json() == []
    # Task itself survives on the board.
    assert [x["text"] for x in client.get("/api/tasks").json()] == ["task"]


def test_bind_requires_both_date_and_time(client):
    p = _project(client, "Proj")
    t = _task(client, p["id"], "task")
    # date without time -> 422
    assert client.put(
        f"/api/tasks/{t['id']}/event", json={"event_date": "2026-07-04"}
    ).status_code == 422


def test_deadline_and_event_date_are_independent(client):
    p = _project(client, "Proj")
    t = _task(client, p["id"], "task")
    client.patch(f"/api/tasks/{t['id']}", json={"deadline": "2026-12-31"})
    client.put(
        f"/api/tasks/{t['id']}/event",
        json={"event_date": "2026-07-04", "event_time": "10:00"},
    )
    tasks = {x["id"]: x for x in client.get("/api/tasks").json()}
    task = tasks[t["id"]]
    assert task["deadline"] == "2026-12-31"
    assert task["event_date"] == "2026-07-04"
    # Calendar uses event_date, not the deadline.
    events = client.get("/api/events").json()
    assert events[0]["event_date"] == "2026-07-04"


def test_deleting_project_task_event_removes_from_calendar(client):
    p = _project(client, "Proj")
    t = _task(client, p["id"], "task")
    client.put(
        f"/api/tasks/{t['id']}/event",
        json={"event_date": "2026-07-04", "event_time": "10:00"},
    )
    client.delete(f"/api/tasks/{t['id']}")
    assert client.get("/api/events").json() == []


def test_project_task_event_reflects_done_and_text(client):
    p = _project(client, "Proj")
    t = _task(client, p["id"], "task")
    client.put(
        f"/api/tasks/{t['id']}/event",
        json={"event_date": "2026-07-04", "event_time": "10:00"},
    )
    client.patch(f"/api/tasks/{t['id']}", json={"done": True, "text": "renamed"})
    e = client.get("/api/events").json()[0]
    assert e["done"] is True and e["text"] == "renamed"


def test_event_routes_reject_project_task(client):
    # The /api/events PATCH/DELETE are only for standalone events.
    p = _project(client, "Proj")
    t = _task(client, p["id"], "task")
    client.put(
        f"/api/tasks/{t['id']}/event",
        json={"event_date": "2026-07-04", "event_time": "10:00"},
    )
    assert client.patch(f"/api/events/{t['id']}", json={"text": "z"}).status_code == 400
    assert client.delete(f"/api/events/{t['id']}").status_code == 400


def test_event_patch_missing(client):
    assert client.patch("/api/events/999", json={"text": "x"}).status_code == 404
