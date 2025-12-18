// src/pages/DriversPage.tsx
/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from "react";

type Driver = {
  id: number;
  name: string;
  rut?: string | null;
};

const apiBaseUrl =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) || "http://localhost:8000").replace(
    /\/+$/,
    ""
  );

const DriversPage = () => {
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [rut, setRut] = useState("");

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const loadDrivers = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`${apiBaseUrl}/drivers`);
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Error ${res.status}: ${text}`);
      }
      const data: Driver[] = await res.json();
      setDrivers(data);
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "No se pudieron cargar los choferes.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDrivers();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setSaveError("El nombre del chofer es obligatorio.");
      return;
    }

    try {
      setSaving(true);
      setSaveError(null);

      const res = await fetch(`${apiBaseUrl}/drivers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          rut: rut.trim() || null,
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Error ${res.status}: ${text}`);
      }

      setName("");
      setRut("");
      await loadDrivers();
    } catch (e: any) {
      console.error(e);
      setSaveError(e?.message || "No se pudo crear el chofer.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="card entity-page">
      {/* Formulario creación chofer */}
      <div>
        <div className="card-header">
          <div>
            <div className="card-title">Choferes</div>
            <div className="card-subtitle">
              Registro de choferes que operan las máquinas en el campo.
            </div>
          </div>
        </div>

        <form className="form-grid" onSubmit={handleCreate}>
          <div className="form-field">
            <label className="form-label">Nombre del chofer *</label>
            <input
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ej: Juan Pérez"
            />
          </div>

          <div className="form-field">
            <label className="form-label">RUT</label>
            <input
              className="form-input"
              value={rut}
              onChange={(e) => setRut(e.target.value)}
              placeholder="11.111.111-1"
            />
          </div>

          {saveError && <div className="tracker-error">⚠️ {saveError}</div>}

          <div>
            <button
              type="submit"
              className="form-button-primary"
              disabled={saving}
            >
              {saving ? "Guardando..." : "Agregar chofer"}
            </button>
          </div>
        </form>
      </div>

      {/* Tabla choferes */}
      <div>
        <div className="entity-table-wrapper">
          {error && <div className="tracker-error">⚠️ {error}</div>}
          {loading ? (
            <div className="sessions-loading">Cargando choferes…</div>
          ) : drivers.length === 0 ? (
            <div className="sessions-empty">
              No hay choferes registrados. Agrega el primero con el formulario.
            </div>
          ) : (
            <table className="entity-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Nombre</th>
                  <th>RUT</th>
                </tr>
              </thead>
              <tbody>
                {drivers.map((d) => (
                  <tr key={d.id}>
                    <td>{d.id}</td>
                    <td>{d.name}</td>
                    <td>{d.rut || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </section>
  );
};

export default DriversPage;
