import React, { useState } from "react";
import { projectLabel } from "./helpers.js";

export default function DayPanel({ slots, projects, tasks, onSave }) {
  const [editingIndex, setEditingIndex] = useState(null);

  const taskById = new Map(tasks.map((t) => [t.id, t]));
  const projectById = new Map(projects.map((p) => [p.id, p]));

  // Which slot currently holds each task (for "already in slot N" hints).
  const slotOfTask = new Map();
  slots.forEach((s) => s.task_ids.forEach((id) => slotOfTask.set(id, s.index)));

  return (
    <section className="day-panel">
      <h2 className="day-title">Дела на день</h2>
      <div className="slots">
        {slots.map((slot) => (
          <div className="slot" key={slot.index}>
            <div className="slot-head">
              <span className="slot-name">Слот {slot.index + 1}</span>
              <button
                className="ghost small"
                onClick={() => setEditingIndex(slot.index)}
              >
                Изменить
              </button>
            </div>
            <ul className="slot-tasks">
              {slot.task_ids
                .map((id) => taskById.get(id))
                .filter(Boolean)
                .map((task) => {
                  const project = projectById.get(task.project_id);
                  return (
                    <li
                      key={task.id}
                      className={task.done ? "done" : ""}
                      title={project ? projectLabel(project) : ""}
                    >
                      {project && project.icon ? project.icon + " " : ""}
                      {task.text}
                    </li>
                  );
                })}
              {slot.task_ids.filter((id) => taskById.has(id)).length === 0 && (
                <li className="muted empty-task">пусто</li>
              )}
            </ul>
          </div>
        ))}
      </div>

      {editingIndex !== null && (
        <SlotEditor
          index={editingIndex}
          currentIds={slots[editingIndex].task_ids}
          slotOfTask={slotOfTask}
          projects={projects}
          tasks={tasks}
          onCancel={() => setEditingIndex(null)}
          onSave={async (ids) => {
            await onSave(editingIndex, ids);
            setEditingIndex(null);
          }}
        />
      )}
    </section>
  );
}

function SlotEditor({
  index,
  currentIds,
  slotOfTask,
  projects,
  tasks,
  onSave,
  onCancel,
}) {
  // Selection starts from the current contents; preserves their order.
  const [selected, setSelected] = useState(() => [...currentIds]);

  function toggle(id) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  const byProject = projects.map((p) => ({
    project: p,
    tasks: tasks.filter((t) => t.project_id === p.id),
  }));

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Слот {index + 1}: выбор задач</h3>
        <div className="modal-body">
          {byProject.every((g) => g.tasks.length === 0) && (
            <div className="muted">Нет задач для выбора.</div>
          )}
          {byProject.map(({ project, tasks }) =>
            tasks.length === 0 ? null : (
              <div className="select-group" key={project.id}>
                <div className="select-group-title">
                  {projectLabel(project)}
                </div>
                {tasks.map((task) => {
                  const inOther =
                    slotOfTask.has(task.id) &&
                    slotOfTask.get(task.id) !== index &&
                    !selected.includes(task.id);
                  return (
                    <label key={task.id} className="select-row">
                      <input
                        type="checkbox"
                        checked={selected.includes(task.id)}
                        onChange={() => toggle(task.id)}
                      />
                      <span className={task.done ? "done" : ""}>{task.text}</span>
                      {inOther && (
                        <span className="hint">
                          (в слоте {slotOfTask.get(task.id) + 1})
                        </span>
                      )}
                    </label>
                  );
                })}
              </div>
            )
          )}
        </div>
        <div className="editor-actions">
          <button type="button" onClick={() => onSave(selected)}>
            Сохранить
          </button>
          <button type="button" className="ghost" onClick={onCancel}>
            Отмена
          </button>
        </div>
      </div>
    </div>
  );
}
