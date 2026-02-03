// src/pages/DriversPage.tsx
/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useState, Fragment } from "react";

type Driver = {
  id: number;
  name: string;
  rut?: string | null;
};

const apiBaseUrl =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) || "http://localhost:8000").replace(/\/+$/, "");

async function safeFetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Error ${res.status}: ${text}`);
  }
  return (await res.json()) as T;
}

const DriversPage = () => {
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [saving, setSaving] = useState(false);

  // selección + edición inline
  const [selectedDriverId, setSelectedDriverId] = useState<number | null>(null);
  const [editingDriverId, setEditingDriverId] = useState<number | null>(null);
  const [isInlineEditing, setIsInlineEditing] = useState(false);

  const [drvName, setDrvName] = useState("");
  const [drvRut, setDrvRut] = useState("");

  const [saveError, setSaveError] = useState<string | null>(null);

  // new row
  const [newName, setNewName] = useState("");
  const [newRut, setNewRut] = useState("");
  const [newRowError, setNewRowError] = useState<string | null>(null);

  const selectedDriver = useMemo(
    () => drivers.find((d) => d.id === selectedDriverId) ?? null,
    [drivers, selectedDriverId]
  );

  const loadDrivers = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await safeFetchJson<Driver[]>(`${apiBaseUrl}/drivers`);
      setDrivers(data);
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "No se pudieron cargar los choferes.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDrivers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // si el seleccionado ya no existe, limpiar selección
    if (selectedDriverId != null && !drivers.some((d) => d.id === selectedDriverId)) {
      setSelectedDriverId(null);
      setIsInlineEditing(false);
      setEditingDriverId(null);
      setSaveError(null);
    }
  }, [drivers, selectedDriverId]);

  const onSelectRow = (d: Driver) => {
    if (selectedDriverId === d.id) return; // evita cortar edición al clickear inputs
    setSelectedDriverId(d.id);
    setIsInlineEditing(false);
    setEditingDriverId(null);
    setSaveError(null);
  };

  const startEditDriver = (d: Driver) => {
    setSelectedDriverId(d.id);
    setEditingDriverId(d.id);
    setIsInlineEditing(true);
    setSaveError(null);

    setDrvName(d.name ?? "");
    setDrvRut(d.rut ?? "");
  };

  const cancelEdit = () => {
    setIsInlineEditing(false);
    setEditingDriverId(null);
    setSaveError(null);
    setDrvName("");
    setDrvRut("");
  };

  const validateAndBuildEditBody = () => {
    if (!drvName.trim()) return { ok: false as const, error: "El nombre del chofer es obligatorio." };

    return {
      ok: true as const,
      body: {
        name: drvName.trim(),
        rut: drvRut.trim() || null,
      },
    };
  };

  const saveInlineDriver = async () => {
    if (editingDriverId == null) {
      setSaveError("No hay chofer en edición.");
      return;
    }

    const v = validateAndBuildEditBody();
    if (!v.ok) {
      setSaveError(v.error);
      return;
    }

    try {
      setSaving(true);
      setSaveError(null);
      setError(null);

      await safeFetchJson(`${apiBaseUrl}/drivers/${editingDriverId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(v.body),
      });

      cancelEdit();
      await loadDrivers();
    } catch (e: any) {
      console.error(e);
      setSaveError(e?.message || "No se pudo guardar el chofer.");
    } finally {
      setSaving(false);
    }
  };

  const validateAndBuildNewBody = () => {
    if (!newName.trim()) return { ok: false as const, error: "El nombre del chofer es obligatorio." };
    return {
      ok: true as const,
      body: {
        name: newName.trim(),
        rut: newRut.trim() || null,
      },
    };
  };

  const resetNewRow = () => {
    setNewName("");
    setNewRut("");
    setNewRowError(null);
  };

  const createNewDriverFromRow = async () => {
    const v = validateAndBuildNewBody();
    if (!v.ok) {
      setNewRowError(v.error);
      return;
    }

    try {
      setSaving(true);
      setNewRowError(null);
      setError(null);

      await safeFetchJson(`${apiBaseUrl}/drivers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(v.body),
      });

      resetNewRow();
      await loadDrivers();
    } catch (e: any) {
      console.error(e);
      setNewRowError(e?.message || "No se pudo crear el chofer.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteDriver = async (id: number) => {
    const ok = window.confirm("¿Eliminar este chofer? Esta acción no se puede deshacer.");
    if (!ok) return;

    try {
      setSaving(true);
      setError(null);

      await safeFetchJson(`${apiBaseUrl}/drivers/${id}`, { method: "DELETE" });

      if (selectedDriverId === id) setSelectedDriverId(null);
      if (editingDriverId === id) cancelEdit();
      await loadDrivers();
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "No se pudo eliminar el chofer.");
    } finally {
      setSaving(false);
    }
  };

  const canAddNew = Boolean(newName.trim());

  return (
    <section className="card entity-page">
      <div className="card-header">
        <div>
          <div className="card-title">Choferes</div>
          <div className="card-subtitle">Registro de choferes que operan las máquinas en el campo.</div>
        </div>
      </div>

      {error && <div className="tracker-error">⚠️ {error}</div>}

      <div className="entity-table-wrapper">
        {loading ? (
          <div className="sessions-loading">Cargando choferes…</div>
        ) : drivers.length === 0 ? (
          <div className="sessions-empty">No hay choferes registrados. Agrega el primero en la última fila.</div>
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
              {drivers.map((d) => {
                const isSelected = selectedDriverId === d.id;
                const isEditingThisRow = isInlineEditing && editingDriverId === d.id && isSelected;

                return (
                  <Fragment key={d.id}>
                    <tr
                      onClick={() => onSelectRow(d)}
                      style={{ cursor: "pointer", background: isSelected ? "rgba(0,0,0,0.04)" : undefined }}
                      title="Click para seleccionar"
                    >
                      <td>{d.id}</td>

                      <td>
                        {isEditingThisRow ? (
                          <input className="form-input" value={drvName} onChange={(e) => setDrvName(e.target.value)} placeholder="Nombre" />
                        ) : (
                          d.name
                        )}
                      </td>

                      <td>
                        {isEditingThisRow ? (
                          <input className="form-input" value={drvRut} onChange={(e) => setDrvRut(e.target.value)} placeholder="11.111.111-1" />
                        ) : (
                          d.rut || "—"
                        )}
                      </td>
                    </tr>
                  </Fragment>
                );
              })}

              {/* NEW ROW */}
              <tr style={{ background: "rgba(0,0,0,0.02)" }}>
                <td style={{ fontWeight: 700 }}>+</td>

                <td>
                  <input
                    className="form-input"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="Nuevo chofer"
                  />
                </td>

                <td>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <input className="form-input" value={newRut} onChange={(e) => setNewRut(e.target.value)} placeholder="RUT (opcional)" />

                    {canAddNew && (
                      <button type="button" className="form-button-primary" onClick={() => void createNewDriverFromRow()} disabled={saving}>
                        {saving ? "Agregando..." : "Agregar"}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        )}
      </div>

      {/* Buttons below table */}
      <div style={{ marginTop: 10 }}>
        <div className="card-subtitle" style={{ marginBottom: 8 }}>
          {selectedDriver ? (
            <>
              Seleccionado: <b>#{selectedDriver.id}</b> — {selectedDriver.name}
            </>
          ) : (
            "Selecciona un chofer para editar / borrar."
          )}
        </div>

        {saveError && <div className="tracker-error">⚠️ {saveError}</div>}
        {newRowError && <div className="tracker-error">⚠️ {newRowError}</div>}

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {!isInlineEditing ? (
            <button
              type="button"
              className="form-button-primary"
              disabled={!selectedDriver}
              onClick={() => selectedDriver && startEditDriver(selectedDriver)}
            >
              Editar
            </button>
          ) : (
            <>
              <button type="button" className="form-button-primary" onClick={() => void saveInlineDriver()} disabled={saving}>
                {saving ? "Guardando..." : "Guardar cambios"}
              </button>

              <button type="button" className="form-button-primary" onClick={cancelEdit} disabled={saving}>
                Cancelar
              </button>
            </>
          )}

          <button
            type="button"
            className="form-button-primary"
            disabled={!selectedDriver || saving}
            onClick={() => selectedDriver && void handleDeleteDriver(selectedDriver.id)}
          >
            Borrar
          </button>
        </div>
      </div>
    </section>
  );
};

export default DriversPage;
