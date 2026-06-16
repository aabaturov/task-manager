import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import Login from "./Login.jsx";
import Board from "./Board.jsx";

export default function App() {
  const [authed, setAuthed] = useState(null); // null = unknown / loading

  useEffect(() => {
    api
      .me()
      .then(() => setAuthed(true))
      .catch(() => setAuthed(false));
  }, []);

  if (authed === null) {
    return <div className="centered muted">Загрузка…</div>;
  }

  if (!authed) {
    return <Login onLoggedIn={() => setAuthed(true)} />;
  }

  return <Board onLoggedOut={() => setAuthed(false)} />;
}
