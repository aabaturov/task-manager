// Local date helpers (use the browser's timezone/locale per SPEC-001 F3/F7).

export function todayStr() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function isOverdue(task) {
  // A done task is never shown as overdue (SPEC-001 F3 edge case).
  return !!task.deadline && !task.done && task.deadline < todayStr();
}

export function formatDeadline(s) {
  if (!s) return "";
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString();
}

export function projectLabel(project) {
  const icon = (project.icon || "").trim();
  return icon ? `${icon} ${project.name}` : project.name;
}

// ---------------------------------------------------------------- calendar
// Build a YYYY-MM-DD string from a Date (in the browser's local time).
export function dateToStr(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const MONTH_NAMES = [
  "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
];

export function monthTitle(year, month) {
  return `${MONTH_NAMES[month]} ${year}`;
}

// Weeks (Mon-first) covering the whole month, padded with neighbouring days.
// Returns an array of weeks; each week is an array of 7 {dateStr, inMonth}.
export function monthGrid(year, month) {
  const first = new Date(year, month, 1);
  // JS getDay(): 0=Sun..6=Sat. We want Monday-first columns.
  const offset = (first.getDay() + 6) % 7;
  const start = new Date(year, month, 1 - offset);

  const weeks = [];
  let cursor = new Date(start);
  for (let w = 0; w < 6; w++) {
    const week = [];
    for (let d = 0; d < 7; d++) {
      week.push({
        dateStr: dateToStr(cursor),
        inMonth: cursor.getMonth() === month,
        day: cursor.getDate(),
      });
      cursor = new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() + 1);
    }
    weeks.push(week);
    // Stop after we have covered the month and finished the current week.
    if (cursor.getMonth() !== month && weeks.length >= 4 && week[6].inMonth === false) {
      // continue to fill 6 rows for a stable height only if month spilled.
    }
  }
  return weeks;
}

export function formatTime(s) {
  if (!s) return "";
  // event_time arrives as "HH:MM:SS"; show HH:MM.
  return s.slice(0, 5);
}
