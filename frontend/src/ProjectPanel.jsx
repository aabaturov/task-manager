import React, { useEffect, useRef, useState } from "react";
import TaskItem from "./TaskItem.jsx";
import Icon from "./Icon.jsx";

const QUICK_ICONS = ["📋", "💼", "🏠", "🛒", "💡", "📚", "💪", "✈️", "🎯", "🔧"];

export default function ProjectPanel({
  project,
  tasks,
  onAddTask,
  onUpdateTask,
  onRemoveTask,
  onReorder,
  onUpdateProject,
  onRemoveProject,
}) {
  const [text, setText] = useState("");
  const [editingProject, setEditingProject] = useState(false);

  // Local task order for live drag feedback; resynced when props change.
  const [order, setOrder] = useState(tasks);
  const dragId = useRef(null);
  const [dragVisualId, setDragVisualId] = useState(null);
  const listRef = useRef(null);

  // Keep the latest order reachable from the (drag-start) pointerup closure.
  const orderRef = useRef(order);
  orderRef.current = order;

  useEffect(() => {
    setOrder(tasks);
  }, [tasks]);

  async function submit(e) {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    setText("");
    await onAddTask(project.id, value);
  }

  // ----- drag reorder (pointer events: works with mouse and touch) --------
  function onDragStart(e, taskId) {
    e.preventDefault();
    dragId.current = taskId;
    setDragVisualId(taskId);
    document.body.classList.add("dragging-active");
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
  }

  function onPointerMove(e) {
    const id = dragId.current;
    if (id == null || !listRef.current) return;
    const items = [...listRef.current.querySelectorAll("[data-task-id]")];
    const others = items
      .filter((el) => Number(el.dataset.taskId) !== id)
      .map((el) => {
        const r = el.getBoundingClientRect();
        return { id: Number(el.dataset.taskId), mid: r.top + r.height / 2 };
      });
    let insertAt = others.length;
    for (let i = 0; i < others.length; i++) {
      if (e.clientY < others[i].mid) {
        insertAt = i;
        break;
      }
    }
    setOrder((prev) => {
      const dragged = prev.find((t) => t.id === id);
      if (!dragged) return prev;
      const without = prev.filter((t) => t.id !== id);
      return [...without.slice(0, insertAt), dragged, ...without.slice(insertAt)];
    });
  }

  async function onPointerUp() {
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
    document.body.classList.remove("dragging-active");
    const id = dragId.current;
    dragId.current = null;
    setDragVisualId(null);
    if (id == null) return;
    const ids = orderRef.current.map((t) => t.id);
    const original = tasks.map((t) => t.id);
    if (ids.join(",") !== original.join(",")) {
      await onReorder(project.id, ids);
    }
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2 title={project.name}>
          {project.icon && <span className="proj-icon">{project.icon}</span>}
          {project.name}
        </h2>
        <div className="panel-head-actions">
          <button
            className={"icon" + (project.pinned ? " on" : "")}
            title={project.pinned ? "Открепить" : "Закрепить"}
            aria-label={project.pinned ? "Открепить" : "Закрепить"}
            onClick={() => onUpdateProject(project.id, { pinned: !project.pinned })}
          >
            <Icon name="pin" size={17} />
          </button>
          <button
            className="icon"
            title="Настройки проекта"
            aria-label="Настройки проекта"
            onClick={() => setEditingProject((v) => !v)}
          >
            <Icon name="pencil" size={17} />
          </button>
          <button
            className="icon"
            title="Удалить проект"
            aria-label="Удалить проект"
            onClick={() => onRemoveProject(project)}
          >
            <Icon name="x" size={17} />
          </button>
        </div>
      </div>

      {editingProject && (
        <ProjectEditor
          project={project}
          onSave={async (patch) => {
            await onUpdateProject(project.id, patch);
            setEditingProject(false);
          }}
          onCancel={() => setEditingProject(false)}
        />
      )}

      <ul className="tasks" ref={listRef}>
        {order.map((task) => (
          <TaskItem
            key={task.id}
            task={task}
            onUpdate={onUpdateTask}
            onDelete={onRemoveTask}
            onDragStart={onDragStart}
            dragging={dragVisualId === task.id}
          />
        ))}
        {order.length === 0 && (
          <li className="muted empty-task">Нет задач</li>
        )}
      </ul>

      <form className="add-task" onSubmit={submit}>
        <input
          type="text"
          placeholder="Добавить задачу…"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button type="submit" aria-label="Добавить задачу">
          <Icon name="plus" size={18} />
        </button>
      </form>
    </section>
  );
}

function ProjectEditor({ project, onSave, onCancel }) {
  const [name, setName] = useState(project.name);
  const [icon, setIcon] = useState(project.icon || "");
  const [type, setType] = useState(project.type || "local");
  const [error, setError] = useState("");

  async function save() {
    if (!name.trim()) {
      setError("Название не может быть пустым");
      return;
    }
    try {
      await onSave({ name: name.trim(), icon: icon.trim(), type });
    } catch (err) {
      setError(err.message || "Не удалось сохранить");
    }
  }

  return (
    <div className="project-editor">
      <label>
        Название
        <input value={name} onChange={(e) => setName(e.target.value)} />
      </label>

      <label>
        Значок
        <div className="icon-picker">
          <input
            className="icon-input"
            value={icon}
            placeholder="эмодзи"
            maxLength={8}
            onChange={(e) => setIcon(e.target.value)}
          />
          {QUICK_ICONS.map((q) => (
            <button
              key={q}
              type="button"
              className={"emoji" + (icon === q ? " sel" : "")}
              onClick={() => setIcon(q)}
            >
              {q}
            </button>
          ))}
          <button type="button" className="emoji" onClick={() => setIcon("")}>
            нет
          </button>
        </div>
      </label>

      <label>
        Тип
        <select value={type} onChange={(e) => setType(e.target.value)}>
          <option value="local">Локальный</option>
          <option value="global">Глобальный</option>
        </select>
      </label>

      {error && <div className="error">{error}</div>}

      <div className="editor-actions">
        <button type="button" onClick={save}>
          Сохранить
        </button>
        <button type="button" className="ghost" onClick={onCancel}>
          Отмена
        </button>
      </div>
    </div>
  );
}
