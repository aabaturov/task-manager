import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import ProjectPanel from "./ProjectPanel.jsx";
import DayPanel from "./DayPanel.jsx";
import LightTasksPanel from "./LightTasksPanel.jsx";
import CalendarPanel from "./CalendarPanel.jsx";

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
  const [lightTasks, setLightTasks] = useState([]);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");

  async function reload() {
    try {
      const [p, t, s, l, e] = await Promise.all([
        api.listProjects(),
        api.listTasks(),
        api.getDaySlots(),
        api.listLightTasks(),
        api.listEvents(),
      ]);
      setProjects(p);
      setTasks(t);
      setSlots(s);
      setLightTasks(l);
      setEvents(e);
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
      await api.createProject(name.trim(), null, "temporary");
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

  // ----- light tasks (SPEC-004 Feature 2) ---------------------------------
  async function addLightTask(text) {
    await api.createLightTask(text);
    reload();
  }
  async function toggleLightTask(id, done) {
    await api.updateLightTask(id, { done });
    reload();
  }
  async function removeLightTask(id) {
    await api.deleteLightTask(id);
    reload();
  }

  // ----- calendar events (SPEC-004 Feature 3) -----------------------------
  async function createEvent(text, eventDate, eventTime) {
    await api.createEvent(text, eventDate, eventTime);
    reload();
  }
  async function updateEvent(id, patch) {
    await api.updateEvent(id, patch);
    await reload();
  }
  async function removeEvent(id) {
    await api.deleteEvent(id);
    reload();
  }

  async function logout() {
    await api.logout();
    onLoggedOut();
  }

  // ----- board organisation (SPEC-004 Feature 1) --------------------------
  // Board below the three top blocks, split into groups:
  //   pinned (default per spec note, awaiting confirmation) -> temporary ->
  //   permanent. Empty groups are not rendered.
  const pinned = projects
    .filter((p) => p.pinned)
    .sort((a, b) => (a.pinned_at || "").localeCompare(b.pinned_at || ""));
  const temporary = projects.filter((p) => !p.pinned && p.type === "temporary");
  const permanent = projects.filter((p) => !p.pinned && p.type === "permanent");
  // Show group headers when more than one group is non-empty.
  const nonEmptyGroups = [pinned, temporary, permanent].filter(
    (g) => g.length > 0
  ).length;
  const showGroupHeaders = nonEmptyGroups > 1;

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

      {/* SPEC-004 Feature 1: three named top blocks in a row. */}
      <div className="top-blocks">
        <DayPanel
          slots={slots}
          projects={projects}
          tasks={tasks}
          onUpdateTask={updateTask}
          onSave={saveSlot}
        />
        <LightTasksPanel
          items={lightTasks}
          onAdd={addLightTask}
          onToggle={toggleLightTask}
          onDelete={removeLightTask}
        />
        <CalendarPanel
          events={events}
          projects={projects}
          onCreateEvent={createEvent}
          onUpdateEvent={updateEvent}
          onDeleteEvent={removeEvent}
        />
      </div>

      {/* Project board below the three blocks. */}
      <div className="normal-board">
        {renderGroup("Закреплённые", pinned)}
        {renderGroup("Временные", temporary)}
        {renderGroup("Постоянные", permanent)}
      </div>

      {projects.length === 0 && (
        <div className="empty muted">
          Пока нет проектов. Создай первый кнопкой «+ Проект».
        </div>
      )}
    </div>
  );
}
