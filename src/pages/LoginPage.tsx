/* eslint-disable @typescript-eslint/no-explicit-any */
// src/pages/LoginPage.tsx
import React, { useState } from "react";
import { useAuthWeb } from "../services/AuthContext";

export default function LoginPage() {
  const { login } = useAuthWeb();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      await login(username.trim(), password);
    } catch (e: any) {
      const msg =
        e?.detail?.detail ||
        e?.message ||
        "No se pudo iniciar sesión";
      setErr(String(msg));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell" style={{ padding: 24, maxWidth: 420, margin: "0 auto" }}>
      <h2 style={{ marginBottom: 8 }}>Tracker Steps</h2>
      <p style={{ opacity: 0.8, marginTop: 0 }}>Ingresa con tus credenciales.</p>

      <form onSubmit={onSubmit} style={{ display: "grid", gap: 10, marginTop: 16 }}>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Usuario"
          autoComplete="username"
          style={{ padding: 12, borderRadius: 10 }}
        />
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Contraseña"
          type="password"
          autoComplete="current-password"
          style={{ padding: 12, borderRadius: 10 }}
        />

        {err && (
          <div style={{ padding: 12, borderRadius: 10, border: "1px solid #ef4444" }}>
            {err}
          </div>
        )}

        <button type="submit" disabled={loading} className="app-nav-button">
          {loading ? "Ingresando..." : "Ingresar"}
        </button>
      </form>
    </div>
  );
}
