import React, { useEffect, useState } from "react";
import { api } from "./api.js";

export default function Board({ onLoggedOut }) {
  const [projects, setProjects] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [error, setError] = useState("");

  async function reload() {
    try {
      const [p, t] = await Promise.all([api.listProjects(), api.listTasks()]);
      setProjects(p);
      setTasks(t);
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
      await api.createProject(name.trim());
      reload();
    } catch (err) {
      alert(err.message);
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

  async function removeTask(taskId) {
    await api.deleteTask(taskId);
    reload();
  }

  async function logout() {
    await api.logout();
    onLoggedOut();
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>Менеджер задач</h1>
        <div className="topbar-actions">
          <button onClick={addProject}>+ Проект</button>
          <button className="ghost" onClick={logout}>
            Выйти
          </button>
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      {projects.length === 0 ? (
        <div className="empty muted">
          Пока нет проектов. Создай первый кнопкой «+ Проект».
        </div>
      ) : (
        <div className="board">
          {projects.map((project) => (
            <ProjectPanel
              key={project.id}
              project={project}
              tasks={tasks.filter((t) => t.project_id === project.id)}
              onAddTask={addTask}
              onRemoveTask={removeTask}
              onRemoveProject={removeProject}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ProjectPanel({
  project,
  tasks,
  onAddTask,
  onRemoveTask,
  onRemoveProject,
}) {
  const [text, setText] = useState("");

  async function submit(e) {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    setText("");
    await onAddTask(project.id, value);
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2 title={project.name}>{project.name}</h2>
        <button
          className="icon"
          title="Удалить проект"
          onClick={() => onRemoveProject(project)}
        >
          ×
        </button>
      </div>

      <ul className="tasks">
        {tasks.map((task) => (
          <li key={task.id}>
            <span>{task.text}</span>
            <button
              className="icon"
              title="Удалить задачу"
              onClick={() => onRemoveTask(task.id)}
            >
              ×
            </button>
          </li>
        ))}
        {tasks.length === 0 && <li className="muted empty-task">Нет задач</li>}
      </ul>

      <form className="add-task" onSubmit={submit}>
        <input
          type="text"
          placeholder="Добавить задачу…"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button type="submit">+</button>
      </form>
    </section>
  );
}
