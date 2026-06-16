import React, { useState } from "react";
import { api } from "./api.js";

export default function Login({ onLoggedIn }) {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.login(login, password);
      onLoggedIn();
    } catch (err) {
      setError("Неверный логин или пароль");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="centered">
      <form className="login-card" onSubmit={submit}>
        <h1>Менеджер задач</h1>
        <input
          type="text"
          placeholder="Логин"
          value={login}
          autoFocus
          onChange={(e) => setLogin(e.target.value)}
        />
        <input
          type="password"
          placeholder="Пароль"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <div className="error">{error}</div>}
        <button type="submit" disabled={busy}>
          {busy ? "Вход…" : "Войти"}
        </button>
      </form>
    </div>
  );
}
