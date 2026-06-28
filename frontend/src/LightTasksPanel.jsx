import React, { useState } from "react";
import Icon from "./Icon.jsx";

// SPEC-004 Feature 2: «Лёгкие дела (не забыть)» — a standalone reminder list.
// Add (non-empty text), mark done (strike-through, stays in list), delete.
// Independent from project tasks and the "important" flag.
export default function LightTasksPanel({
  items,
  onAdd,
  onToggle,
  onDelete,
}) {
  const [text, setText] = useState("");

  async function submit(e) {
    e.preventDefault();
    const value = text.trim();
    if (!value) return; // empty / whitespace-only is ignored
    setText("");
    await onAdd(value);
  }

  return (
    <section className="light-panel block">
      <h2 className="block-title">Лёгкие дела (не забыть)</h2>

      <ul className="light-list">
        {items.map((item) => (
          <li
            key={item.id}
            className={"light-item" + (item.done ? " done" : "")}
          >
            <button
              className={"check sm" + (item.done ? " checked" : "")}
              title={item.done ? "Снять отметку" : "Отметить сделанным"}
              aria-label={item.done ? "Снять отметку" : "Отметить сделанным"}
              onClick={() => onToggle(item.id, !item.done)}
            >
              {item.done && <Icon name="check" size={11} strokeWidth={2.4} />}
            </button>
            <span className="light-text">{item.text}</span>
            <button
              className="icon"
              title="Удалить"
              aria-label="Удалить лёгкое дело"
              onClick={() => onDelete(item.id)}
            >
              <Icon name="x" size={15} />
            </button>
          </li>
        ))}
        {items.length === 0 && (
          <li className="muted light-empty">Нет дел</li>
        )}
      </ul>

      <form className="add-light" onSubmit={submit}>
        <input
          type="text"
          placeholder="Не забыть…"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button type="submit" aria-label="Добавить лёгкое дело">
          <Icon name="plus" size={18} />
        </button>
      </form>
    </section>
  );
}
