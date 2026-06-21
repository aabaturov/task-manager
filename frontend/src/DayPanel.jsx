import React, { useState } from "react";
import Icon from "./Icon.jsx";
import { projectLabel } from "./helpers.js";

export default function DayPanel({ slots, projects, tasks, onUpdateTask, onSave }) {
  const [editingIndex, setEditingIndex] = useState(null);

  const taskById = new Map(tasks.map((t) => [t.id, t]));
  const projectById = new Map(projects.map((p) => [p.id, p]));

  // Which slot currently holds each task (for "already in slot N" hints).
  const slotOfTask = new Map();
  slots.forEach((s) => s.task_ids.forEach((id) => slotOfTask.set(id, s.index)));

  return (
    <section className="day-panel">
      <h2 className="day-title">
        <span className="day-pin">
          <Icon name="pin" size={16} />
        </span>
        Дела на день
      </h2>
      <div className="slots">
        {slots.map((slot) => {
          const slotTasks = slot.task_ids
            .map((id) => taskById.get(id))
            .filter(Boolean);
          return (
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
                {slotTasks.map((task) => {
                  const project = projectById.get(task.project_id);
                  return (
                    <li
                      key={task.id}
                      className={"slot-task" + (task.done ? " done" : "")}
                    >
                      <button
                        className={"check sm" + (task.done ? " checked" : "")}
                        title={task.done ? "Снять отметку" : "Отметить сделанным"}
                        aria-label={
                          task.done ? "Снять отметку" : "Отметить сделанным"
                        }
                        onClick={() =>
                          onUpdateTask(task.id, { done: !task.done })
                        }
                      >
                        {task.done && (
                          <Icon name="check" size={11} strokeWidth={2.4} />
                        )}
                      </button>
                      <span className="slot-task-body">
                        <span className="slot-task-text">{task.text}</span>
                        {project && (
                          <span
                            className="slot-task-project"
                            title={projectLabel(project)}
                          >
                            {project.icon ? project.icon + " " : ""}
                            {project.name}
                          </span>
                        )}
                      </span>
                    </li>
                  );
                })}
                {slotTasks.length === 0 && (
                  <li className="slot-empty">
                    <button
                      type="button"
                      className="slot-empty-add"
                      onClick={() => setEditingIndex(slot.index)}
                      aria-label={`Добавить задачи в слот ${slot.index + 1}`}
                    >
                      <Icon name="plus" size={14} strokeWidth={1.8} />
                      <span>добавить</span>
                    </button>
                  </li>
                )}
              </ul>
            </div>
          );
        })}
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
