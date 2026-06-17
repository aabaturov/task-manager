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
