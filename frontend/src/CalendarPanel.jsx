import React, { useMemo, useState } from "react";
import Icon from "./Icon.jsx";
import {
  monthGrid,
  monthTitle,
  todayStr,
  formatTime,
  projectLabel,
} from "./helpers.js";

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

// SPEC-004 Feature 3: a Google-style month grid. Cells show events bound to
// their date. Clicking a day opens its panel: create a standalone event
// (text + required time) and see/manage the full list for that day.
export default function CalendarPanel({
  events,
  projects,
  onCreateEvent,
  onUpdateEvent,
  onDeleteEvent,
}) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [openDay, setOpenDay] = useState(null); // YYYY-MM-DD or null

  const projectById = useMemo(
    () => new Map(projects.map((p) => [p.id, p])),
    [projects]
  );

  // Group events by their date for quick per-cell lookup.
  const byDate = useMemo(() => {
    const map = new Map();
    for (const ev of events) {
      const list = map.get(ev.event_date) || [];
      list.push(ev);
      map.set(ev.event_date, list);
    }
    // Events already arrive sorted by date+time from the API.
    return map;
  }, [events]);

  const weeks = useMemo(() => monthGrid(year, month), [year, month]);
  const today = todayStr();

  function prevMonth() {
    setOpenDay(null);
    if (month === 0) {
      setYear((y) => y - 1);
      setMonth(11);
    } else setMonth((m) => m - 1);
  }
  function nextMonth() {
    setOpenDay(null);
    if (month === 11) {
      setYear((y) => y + 1);
      setMonth(0);
    } else setMonth((m) => m + 1);
  }
  function goToday() {
    setOpenDay(null);
    setYear(now.getFullYear());
    setMonth(now.getMonth());
  }

  return (
    <section className="calendar-panel block">
      <div className="cal-head">
        <h2 className="block-title">Календарь</h2>
        <div className="cal-nav">
          <button className="ghost small" onClick={prevMonth} aria-label="Прошлый месяц">
            ‹
          </button>
          <button className="ghost small" onClick={goToday}>
            Сегодня
          </button>
          <button className="ghost small" onClick={nextMonth} aria-label="Следующий месяц">
            ›
          </button>
        </div>
      </div>
      <div className="cal-month">{monthTitle(year, month)}</div>

      <div className="cal-weekdays">
        {WEEKDAYS.map((w) => (
          <div className="cal-weekday" key={w}>
            {w}
          </div>
        ))}
      </div>

      <div className="cal-grid">
        {weeks.map((week, wi) => (
          <div className="cal-week" key={wi}>
            {week.map((cell) => {
              const dayEvents = byDate.get(cell.dateStr) || [];
              const isToday = cell.dateStr === today;
              return (
                <button
                  key={cell.dateStr}
                  type="button"
                  className={
                    "cal-cell" +
                    (cell.inMonth ? "" : " out") +
                    (isToday ? " today" : "")
                  }
                  onClick={() => setOpenDay(cell.dateStr)}
                  title={`Открыть ${cell.dateStr}`}
                >
                  <span className="cal-daynum">{cell.day}</span>
                  <span className="cal-events">
                    {dayEvents.slice(0, 3).map((ev) => (
                      <span
                        key={ev.id}
                        className={"cal-ev" + (ev.done ? " done" : "")}
                      >
                        {formatTime(ev.event_time)} {ev.text}
                      </span>
                    ))}
                    {dayEvents.length > 3 && (
                      <span className="cal-more">
                        +{dayEvents.length - 3} ещё
                      </span>
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {openDay !== null && (
        <DayModal
          date={openDay}
          events={byDate.get(openDay) || []}
          projectById={projectById}
          onClose={() => setOpenDay(null)}
          onCreateEvent={onCreateEvent}
          onUpdateEvent={onUpdateEvent}
          onDeleteEvent={onDeleteEvent}
        />
      )}
    </section>
  );
}

function DayModal({
  date,
  events,
  projectById,
  onClose,
  onCreateEvent,
  onUpdateEvent,
  onDeleteEvent,
}) {
  const [text, setText] = useState("");
  const [time, setTime] = useState("");
  const [error, setError] = useState("");

  async function create(e) {
    e.preventDefault();
    const value = text.trim();
    if (!value) {
      setError("Введите текст события");
      return;
    }
    if (!time) {
      setError("Время обязательно");
      return;
    }
    setError("");
    try {
      await onCreateEvent(value, date, time);
      setText("");
      setTime("");
    } catch (err) {
      setError(err.message || "Не удалось создать событие");
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>События — {date}</h3>
        <div className="modal-body">
          <ul className="day-events">
            {events.map((ev) => {
              const project = ev.project_id
                ? projectById.get(ev.project_id)
                : null;
              const standalone = !ev.project_id;
              return (
                <li
                  key={ev.id}
                  className={"day-event" + (ev.done ? " done" : "")}
                >
                  <button
                    className={"check sm" + (ev.done ? " checked" : "")}
                    title={ev.done ? "Снять отметку" : "Отметить сделанным"}
                    aria-label={ev.done ? "Снять отметку" : "Отметить сделанным"}
                    disabled={!standalone}
                    onClick={() =>
                      standalone && onUpdateEvent(ev.id, { done: !ev.done })
                    }
                  >
                    {ev.done && <Icon name="check" size={11} strokeWidth={2.4} />}
                  </button>
                  <span className="day-event-time">
                    {formatTime(ev.event_time)}
                  </span>
                  <span className="day-event-text">{ev.text}</span>
                  {project && (
                    <span
                      className="day-event-project"
                      title={projectLabel(project)}
                    >
                      {project.icon ? project.icon + " " : ""}
                      {project.name}
                    </span>
                  )}
                  {standalone && (
                    <button
                      className="icon"
                      title="Удалить событие"
                      aria-label="Удалить событие"
                      onClick={() => onDeleteEvent(ev.id)}
                    >
                      <Icon name="trash" size={15} />
                    </button>
                  )}
                </li>
              );
            })}
            {events.length === 0 && (
              <li className="muted">На этот день событий нет.</li>
            )}
          </ul>

          <form className="add-event" onSubmit={create}>
            <input
              type="text"
              placeholder="Новое событие…"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <input
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              aria-label="Время события"
              required
            />
            <button type="submit" aria-label="Создать событие">
              <Icon name="plus" size={18} />
            </button>
          </form>
          {error && <div className="error">{error}</div>}
        </div>

        <div className="editor-actions">
          <button type="button" className="ghost" onClick={onClose}>
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}
