import React from "react";

// Тонкие линейные иконки одним инлайн-SVG — без внешних зависимостей.
// Цвет наследуется из currentColor, размер — из пропса size (px).
// `filled` заливает фигуру (используется для активной звезды «важное»).

const PATHS = {
  pin: "M9 4h6M10 4l-1 6-3 2.2V14h12v-1.8L15 10l-1-6M12 14v6",
  pencil: "M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z",
  x: "M6 6l12 12M18 6L6 18",
  trash: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6",
  calendar: "M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM4 9h16M8 3v4M16 3v4",
  check: "M5 12.5l4.2 4.2L19 7",
  plus: "M12 5v14M5 12h14",
  star: "M12 3.4l2.6 5.4 5.9.8-4.3 4.2 1 5.9-5.2-2.8-5.2 2.8 1-5.9L3.5 9.6l5.9-.8z",
};

export default function Icon({
  name,
  size = 18,
  filled = false,
  strokeWidth = 1.7,
  className = "",
  ...rest
}) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    xmlns: "http://www.w3.org/2000/svg",
    className,
    "aria-hidden": "true",
    focusable: "false",
    ...rest,
  };

  // Ручка перетаскивания — шесть заполненных точек.
  if (name === "grip") {
    return (
      <svg {...common} fill="currentColor" stroke="none">
        {[6, 12, 18].map((cy) =>
          [9, 15].map((cx) => (
            <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="1.4" />
          ))
        )}
      </svg>
    );
  }

  const d = PATHS[name];
  if (!d) return null;

  if (filled) {
    return (
      <svg {...common} fill="currentColor" stroke="currentColor" strokeWidth="1" strokeLinejoin="round">
        <path d={d} />
      </svg>
    );
  }

  return (
    <svg
      {...common}
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={d} />
    </svg>
  );
}
