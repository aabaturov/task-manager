import React, { useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";
import { isOverdue, formatDeadline } from "./helpers.js";

export default function TaskItem({ task, onUpdate, onDelete, onDragStart, dragging }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(task.text);
  const [showDate, setShowDate] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  useEffect(() => {
    setDraft(task.text);
  }, [task.text]);

  const overdue = isOverdue(task);

  async function saveEdit() {
    const value = draft.trim();
    if (!value) {
      setDraft(task.text);
      setEditing(false);
      return;
    }
    if (value !== task.text) {
      try {
        await onUpdate(task.id, { text: value });
      } catch (err) {
        setError(err.message || "Не удалось сохранить");
        return;
      }
    }
    setEditing(false);
  }

  function onEditKey(e) {
    if (e.key === "Enter") saveEdit();
    if (e.key === "Escape") {
      setDraft(task.text);
      setEditing(false);
    }
  }

  const classes =
    "task" +
    (task.done ? " done" : "") +
    (task.important ? " important" : "") +
    (overdue ? " overdue" : "") +
    (dragging ? " dragging" : "");

  return (
    <li className={classes} data-task-id={task.id}>
      <div className="task-row">
        <button
          className="drag-handle"
          title="Перетащить"
          onPointerDown={(e) => onDragStart(e, task.id)}
          aria-label="Перетащить задачу"
        >
          <Icon name="grip" size={16} />
        </button>

        <button
          className={"check" + (task.done ? " checked" : "")}
          title={task.done ? "Снять отметку" : "Отметить сделанным"}
          aria-label={task.done ? "Снять отметку" : "Отметить сделанным"}
          onClick={() => onUpdate(task.id, { done: !task.done })}
        >
          {task.done && <Icon name="check" size={12} strokeWidth={2.2} />}
        </button>

        <div className="task-body">
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
              {task.important && (
                <Icon name="star" size={13} filled className="task-star-inline" />
              )}
              {task.text}
            </span>
          )}

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
                      aria-label="Убрать дедлайн"
                      onClick={() => onUpdate(task.id, { deadline: null })}
                    >
                      <Icon name="x" size={16} />
                    </button>
                  )}
                </span>
              )}
            </div>
          )}

          {error && <div className="task-error">{error}</div>}
        </div>

        <div className="task-actions">
          <button
            className={"icon star" + (task.important ? " on" : "")}
            title={task.important ? "Убрать «важное»" : "Пометить «важное»"}
            aria-label={task.important ? "Убрать «важное»" : "Пометить «важное»"}
            onClick={() => onUpdate(task.id, { important: !task.important })}
          >
            <Icon name="star" size={17} filled={task.important} />
          </button>
          <button
            className={"icon" + (task.deadline ? " on" : "")}
            title="Дедлайн"
            aria-label="Дедлайн"
            onClick={() => setShowDate((v) => !v)}
          >
            <Icon name="calendar" size={17} />
          </button>
          <button
            className="icon"
            title="Редактировать"
            aria-label="Редактировать"
            onClick={() => setEditing(true)}
          >
            <Icon name="pencil" size={17} />
          </button>
          <button
            className="icon"
            title="Удалить задачу"
            aria-label="Удалить задачу"
            onClick={() => onDelete(task.id)}
          >
            <Icon name="trash" size={17} />
          </button>
        </div>
      </div>
    </li>
  );
}
