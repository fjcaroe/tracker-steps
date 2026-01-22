/* eslint-disable @typescript-eslint/no-explicit-any */
// src/pages/LoginPage.tsx
import React, { useMemo, useState } from "react";
import { useAuthWeb } from "../services/AuthContext";

export default function LoginPage() {
  const { login } = useAuthWeb();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showPw, setShowPw] = useState(false);

  const canSubmit = useMemo(() => {
    return username.trim().length > 0 && password.length > 0 && !loading;
  }, [username, password, loading]);

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
        "No se pudo iniciar sesión. Verifica tus credenciales.";
      setErr(String(msg));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-bg" aria-hidden="true" />

      <div className="login-wrap">
        <div className="login-card card">
          <div className="login-header">
            <div className="login-brand">
              <div className="login-mark" aria-hidden="true">
                TS
              </div>
              <div className="login-brand-text">
                <div className="login-title">Tracker Steps</div>
                <div className="login-subtitle">
                  Accede a monitoreo en vivo, rutas y sesiones históricas
                </div>
              </div>
            </div>
          </div>

          <form className="login-form" onSubmit={onSubmit}>
            <label className="login-label" htmlFor="username">
              Usuario
            </label>
            <div className="login-field">
              <input
                id="username"
                className="login-input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Ej: fernando.caro"
                autoComplete="username"
                inputMode="text"
                spellCheck={false}
              />
            </div>

            <label className="login-label" htmlFor="password">
              Contraseña
            </label>
            <div className="login-field login-field--with-action">
              <input
                id="password"
                className="login-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Ingresa tu contraseña"
                type={showPw ? "text" : "password"}
                autoComplete="current-password"
              />
              <button
                type="button"
                className="login-field-action"
                onClick={() => setShowPw((v) => !v)}
                aria-label={showPw ? "Ocultar contraseña" : "Mostrar contraseña"}
                title={showPw ? "Ocultar" : "Mostrar"}
              >
                {showPw ? "Ocultar" : "Mostrar"}
              </button>
            </div>

            {err && (
              <div className="login-alert" role="alert">
                <div className="login-alert__title">No se pudo iniciar sesión</div>
                <div className="login-alert__msg">{err}</div>
              </div>
            )}

            <button
              type="submit"
              className="login-submit app-nav-button"
              disabled={!canSubmit}
            >
              {loading ? (
                <span className="login-submit__loading">
                  <span className="login-spinner" aria-hidden="true" />
                  Ingresando…
                </span>
              ) : (
                "Ingresar"
              )}
            </button>

            <div className="login-footer">
              <div className="login-footnote">
                Si tienes problemas de acceso, valida tu usuario y contraseña con el
                administrador.
              </div>
            </div>
          </form>
        </div>

        <div className="login-meta">
          <div className="login-meta-chip">
            Seguridad: sesión protegida por token
          </div>
          <div className="login-meta-chip">Ambiente: Web</div>
        </div>
      </div>
    </div>
  );
}
