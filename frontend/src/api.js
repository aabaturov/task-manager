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
  listProjects: () => request("GET", "/api/projects"),
  createProject: (name) => request("POST", "/api/projects", { name }),
  deleteProject: (id) => request("DELETE", `/api/projects/${id}`),
  listTasks: () => request("GET", "/api/tasks"),
  createTask: (project_id, text) =>
    request("POST", "/api/tasks", { project_id, text }),
  deleteTask: (id) => request("DELETE", `/api/tasks/${id}`),
};
