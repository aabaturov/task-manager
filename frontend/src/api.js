async function request(method, path, body) {
  const opts = {
    method,
    headers: {},
    credentials: "same-origin",
  };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (res.status === 401) {
    const err = new Error("unauthorized");
    err.status = 401;
    throw err;
  }
  if (!res.ok) {
    let detail = "Ошибка запроса";
    try {
      const data = await res.json();
      if (data && data.detail) detail = data.detail;
    } catch (e) {
      /* ignore */
    }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  me: () => request("GET", "/api/me"),
  login: (login, password) => request("POST", "/api/login", { login, password }),
  logout: () => request("POST", "/api/logout"),

  // projects
  listProjects: () => request("GET", "/api/projects"),
  createProject: (name, icon, type) =>
    request("POST", "/api/projects", { name, icon, type }),
  updateProject: (id, patch) => request("PATCH", `/api/projects/${id}`, patch),
  deleteProject: (id) => request("DELETE", `/api/projects/${id}`),
  reorderTasks: (projectId, taskIds) =>
    request("POST", `/api/projects/${projectId}/reorder`, { task_ids: taskIds }),

  // tasks
  listTasks: () => request("GET", "/api/tasks"),
  createTask: (project_id, text) =>
    request("POST", "/api/tasks", { project_id, text }),
  updateTask: (id, patch) => request("PATCH", `/api/tasks/${id}`, patch),
  deleteTask: (id) => request("DELETE", `/api/tasks/${id}`),

  // day panel
  getDaySlots: () => request("GET", "/api/day-slots"),
  setDaySlot: (index, taskIds) =>
    request("PUT", `/api/day-slots/${index}`, { task_ids: taskIds }),

  // light tasks ("не забыть") — SPEC-004 Feature 2
  listLightTasks: () => request("GET", "/api/light-tasks"),
  createLightTask: (text) => request("POST", "/api/light-tasks", { text }),
  updateLightTask: (id, patch) =>
    request("PATCH", `/api/light-tasks/${id}`, patch),
  deleteLightTask: (id) => request("DELETE", `/api/light-tasks/${id}`),

  // calendar events — SPEC-004 Feature 3
  listEvents: (start, end) => {
    const q = new URLSearchParams();
    if (start) q.set("start", start);
    if (end) q.set("end", end);
    const qs = q.toString();
    return request("GET", "/api/events" + (qs ? `?${qs}` : ""));
  },
  createEvent: (text, eventDate, eventTime) =>
    request("POST", "/api/events", {
      text,
      event_date: eventDate,
      event_time: eventTime,
    }),
  updateEvent: (id, patch) => request("PATCH", `/api/events/${id}`, patch),
  deleteEvent: (id) => request("DELETE", `/api/events/${id}`),
  setTaskEvent: (taskId, eventDate, eventTime) =>
    request("PUT", `/api/tasks/${taskId}/event`, {
      event_date: eventDate,
      event_time: eventTime,
    }),
};
