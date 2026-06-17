import React, { useEffect, useRef, useState } from "react";
import { formatDeadline, isOverdue } from "./helpers.js";

export default function TaskItem({
  task,
  onUpdate,
  onDelete,
  onDragStart,
  dragging,
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(task.text);
  const [showDate, setShowDate] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  useEffect(() => {
    if (editing) {
      setDraft(task.text);
      setError("");
      setTimeout(() => inputRef.current && inputRef.current.focus(), 0);
    }
  }, [editing, task.text]);

  async function saveEdit() {
    const value = draft.trim();
    if (!value) {
      setError("Текст не может быть пустым");
      return;
    }
    try {
      await onUpdate(task.id, { text: value });
      setEditing(false);
    } catch (err) {
      setError(err.message || "Не удалось сохранить");
    }
  }

  function onEditKey(e) {
    if (e.key === "Enter") saveEdit();
    if (e.key === "Escape") setEditing(false);
  }

  const overdue = isOverdue(task);
  const classes = [
    "task",
    task.done ? "done" : "",
    task.important ? "important" : "",
    overdue ? "overdue" : "",
    dragging ? "dragging" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <li className={classes} data-task-id={task.id}>
      <div className="task-row">
        <button
          className="drag-handle"
          title="Перетащить"
          onPointerDown={(e) => onDragStart(e, task.id)}
          aria-label="Перетащить задачу"
        >
          ⋮⋮
        </button>

        <button
          className={"check" + (task.done ? " checked" : "")}
          title={task.done ? "Снять отметку" : "Отметить сделанным"}
          onClick={() => onUpdate(task.id, { done: !task.done })}
        >
          {task.done ? "✓" : ""}
        </button>

        {editing ? (
          <input
            ref={inputRef}
            className="task-edit"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onEditKey}
            onBlur={saveEdit}
          />
        ) : (
          <span
            className="task-text"
            onDoubleClick={() => setEditing(true)}
            title="Двойной клик — редактировать"
          >
            {task.text}
          </span>
        )}

        <div className="task-actions">
          <button
            className={"icon star" + (task.important ? " on" : "")}
            title={task.important ? "Убрать «важное»" : "Пометить «важное»"}
            onClick={() => onUpdate(task.id, { important: !task.important })}
          >
            {task.important ? "★" : "☆"}
          </button>
          <button
            className={"icon" + (task.deadline ? " on" : "")}
            title="Дедлайн"
            onClick={() => setShowDate((v) => !v)}
          >
            📅
          </button>
          <button
            className="icon"
            title="Редактировать"
            onClick={() => setEditing(true)}
          >
            ✎
          </button>
          <button
            className="icon"
            title="Удалить задачу"
            onClick={() => onDelete(task.id)}
          >
            ×
          </button>
        </div>
      </div>

      {error && <div className="task-error">{error}</div>}

      {(task.deadline || showDate) && (
        <div className="task-deadline">
          {task.deadline && (
            <span className={"deadline-badge" + (overdue ? " overdue" : "")}>
              {overdue ? "просрочено: " : "до "}
              {formatDeadline(task.deadline)}
            </span>
          )}
          {showDate && (
            <span className="deadline-edit">
              <input
                type="date"
                value={task.deadline || ""}
                onChange={(e) =>
                  onUpdate(task.id, { deadline: e.target.value || null })
                }
              />
              {task.deadline && (
                <button
                  className="icon"
                  title="Убрать дедлайн"
                  onClick={() => onUpdate(task.id, { deadline: null })}
                >
                  ×
                </button>
              )}
            </span>
          )}
        </div>
      )}
    </li>
  );
}
