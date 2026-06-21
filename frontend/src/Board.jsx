import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import ProjectPanel from "./ProjectPanel.jsx";
import DayPanel from "./DayPanel.jsx";

function HeaderClock() {
  // Isolated so the per-second tick does not re-render the whole board.
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="clock" title="Локальные дата и время">
      {now.toLocaleString()}
    </div>
  );
}

export default function Board({ onLoggedOut }) {
  const [projects, setProjects] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [slots, setSlots] = useState([
    { index: 0, task_ids: [] },
    { index: 1, task_ids: [] },
    { index: 2, task_ids: [] },
  ]);
  const [error, setError] = useState("");

  async function reload() {
    try {
      const [p, t, s] = await Promise.all([
        api.listProjects(),
        api.listTasks(),
        api.getDaySlots(),
      ]);
      setProjects(p);
      setTasks(t);
      setSlots(s);
    } catch (err) {
      if (err.status === 401) onLoggedOut();
      else setError(err.message);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  async function addProject() {
    const name = window.prompt("Название проекта:");
    if (!name || !name.trim()) return;
    try {
      await api.createProject(name.trim(), null, "local");
      reload();
    } catch (err) {
      alert(err.message);
    }
  }

  async function updateProject(id, patch) {
    try {
      await api.updateProject(id, patch);
      await reload();
    } catch (err) {
      alert(err.message);
      throw err;
    }
  }

  async function removeProject(project) {
    if (!window.confirm(`Удалить проект «${project.name}» со всеми задачами?`))
      return;
    await api.deleteProject(project.id);
    reload();
  }

  async function addTask(projectId, text) {
    await api.createTask(projectId, text);
    reload();
  }

  async function updateTask(id, patch) {
    await api.updateTask(id, patch);
    await reload();
  }

  async function removeTask(taskId) {
    await api.deleteTask(taskId);
    reload();
  }

  async function reorder(projectId, taskIds) {
    await api.reorderTasks(projectId, taskIds);
    reload();
  }

  async function saveSlot(index, taskIds) {
    await api.setDaySlot(index, taskIds);
    reload();
  }

  async function logout() {
    await api.logout();
    onLoggedOut();
  }

  // ----- board organisation (SPEC-001 Feature 6) --------------------------
  // Pinned zone: day panel (always first) + pinned projects (order of pinning).
  // Normal board below: unpinned projects, local then global.
  const pinned = projects
    .filter((p) => p.pinned)
    .sort((a, b) => (a.pinned_at || "").localeCompare(b.pinned_at || ""));
  const local = projects.filter((p) => !p.pinned && p.type === "local");
  const global = projects.filter((p) => !p.pinned && p.type === "global");
  const showGroupHeaders = local.length > 0 && global.length > 0;

  function renderPanel(project) {
    return (
      <ProjectPanel
        key={project.id}
        project={project}
        tasks={tasks.filter((t) => t.project_id === project.id)}
        onAddTask={addTask}
        onUpdateTask={updateTask}
        onRemoveTask={removeTask}
        onReorder={reorder}
        onUpdateProject={updateProject}
        onRemoveProject={removeProject}
      />
    );
  }

  function renderGroup(title, items) {
    if (items.length === 0) return null;
    return (
      <div className="section">
        {showGroupHeaders && <h2 className="section-title">{title}</h2>}
        <div className="board">{items.map(renderPanel)}</div>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>Менеджер задач</h1>
        <div className="topbar-right">
          <HeaderClock />
          <div className="topbar-actions">
            <button onClick={addProject}>+ Проект</button>
            <button className="ghost" onClick={logout}>
              Выйти
            </button>
          </div>
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      {/* Pinned zone — always present, day panel is its first element. */}
      <div className="pinned-zone">
        <DayPanel
          slots={slots}
          projects={projects}
          tasks={tasks}
          onUpdateTask={updateTask}
          onSave={saveSlot}
        />
        {pinned.map(renderPanel)}
      </div>

      {/* Normal board below the zone. */}
      <div className="normal-board">
        {renderGroup("Локальные", local)}
        {renderGroup("Глобальные", global)}
      </div>

      {projects.length === 0 && (
        <div className="empty muted">
          Пока нет проектов. Создай первый кнопкой «+ Проект».
        </div>
      )}
    </div>
  );
}
