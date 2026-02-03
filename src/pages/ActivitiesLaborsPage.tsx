/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useState, Fragment } from "react";

type Activity = { id: number; name: string; code?: string | null };

type Labor = {
  id: number;
  activity_id: number;
  name: string;
  code?: string | null;
  effort_factor?: number | null;
  target_speed_kmh?: number | null;
};

const apiBaseUrl =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) || "http://localhost:8000").replace(/\/+$/, "");

async function safeFetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Error ${res.status}`);
  }
  return (await res.json()) as T;
}

export default function ActivitiesLaborsPage() {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [labors, setLabors] = useState<Labor[]>([]);
  const [laborsByActivity, setLaborsByActivity] = useState<Labor[]>([]);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // filtro labores
  const [filterLaborsActivityId, setFilterLaborsActivityId] = useState<string>("");

  // ========= Inline: ACTIVIDADES =========
  const [selectedActivityId, setSelectedActivityId] = useState<number | null>(null);
  const [editingActivityId, setEditingActivityId] = useState<number | null>(null);
  const [isInlineEditingActivity, setIsInlineEditingActivity] = useState(false);
  const [activityInlineError, setActivityInlineError] = useState<string | null>(null);

  const [activityName, setActivityName] = useState("");
  const [activityCode, setActivityCode] = useState("");

  // new row activity
  const [newActivityName, setNewActivityName] = useState("");
  const [newActivityCode, setNewActivityCode] = useState("");
  const [newActivityRowError, setNewActivityRowError] = useState<string | null>(null);

  // ========= Inline: LABORES =========
  const [selectedLaborId, setSelectedLaborId] = useState<number | null>(null);
  const [editingLaborId, setEditingLaborId] = useState<number | null>(null);
  const [isInlineEditingLabor, setIsInlineEditingLabor] = useState(false);
  const [laborInlineError, setLaborInlineError] = useState<string | null>(null);

  const [laborActivityId, setLaborActivityId] = useState<string>("");
  const [laborName, setLaborName] = useState("");
  const [laborCode, setLaborCode] = useState("");
  const [laborEffortFactor, setLaborEffortFactor] = useState("");
  const [laborTargetSpeed, setLaborTargetSpeed] = useState("");

  // new row labor
  const [newLaborActivityId, setNewLaborActivityId] = useState<string>("");
  const [newLaborName, setNewLaborName] = useState("");
  const [newLaborCode, setNewLaborCode] = useState("");
  const [newLaborEffortFactor, setNewLaborEffortFactor] = useState("");
  const [newLaborTargetSpeed, setNewLaborTargetSpeed] = useState("");
  const [newLaborRowError, setNewLaborRowError] = useState<string | null>(null);

  const parseNumberOrNull = (value: string): number | null => {
    if (!value.trim()) return null;
    const parsed = parseFloat(value.replace(",", "."));
    return Number.isNaN(parsed) ? null : parsed;
  };

  const currentLabors = useMemo(() => {
    return filterLaborsActivityId ? laborsByActivity : labors;
  }, [filterLaborsActivityId, laborsByActivity, labors]);

  const selectedActivity = useMemo(
    () => activities.find((a) => a.id === selectedActivityId) ?? null,
    [activities, selectedActivityId]
  );

  const selectedLabor = useMemo(
    () => currentLabors.find((l) => l.id === selectedLaborId) ?? null,
    [currentLabors, selectedLaborId]
  );

  const getActivityName = (id?: number | null) => {
    if (!id) return "—";
    const a = activities.find((x) => x.id === id);
    return a ? a.name : `#${id}`;
  };

  // ========= Loaders =========
  const loadActivities = async () => {
    const data = await safeFetchJson<Activity[]>(`${apiBaseUrl}/activities`);
    setActivities(data);
  };

  const loadLabors = async (activityId?: number) => {
    const url = activityId ? `${apiBaseUrl}/labors?activity_id=${activityId}` : `${apiBaseUrl}/labors`;
    const data = await safeFetchJson<Labor[]>(url);
    if (activityId) setLaborsByActivity(data);
    else setLabors(data);
  };

  const refreshLabors = async () => {
    await loadLabors();
    if (filterLaborsActivityId) await loadLabors(Number(filterLaborsActivityId));
  };

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        setError(null);
        await loadActivities();
        await loadLabors();
      } catch (e: any) {
        console.error("Error cargando maestros (actividades/labores)", e);
        setError(e?.message || "Error cargando actividades/labores.");
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // al cambiar filtro, carga lista filtrada (o completa)
    void (async () => {
      try {
        setLoading(true);
        setError(null);
        if (!filterLaborsActivityId) await loadLabors();
        else await loadLabors(Number(filterLaborsActivityId));
      } catch (e: any) {
        console.error(e);
        setError(e?.message || "No se pudieron cargar labores.");
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterLaborsActivityId]);

  // limpiar selección si desaparece
  useEffect(() => {
    if (selectedActivityId != null && !activities.some((a) => a.id === selectedActivityId)) {
      setSelectedActivityId(null);
      setEditingActivityId(null);
      setIsInlineEditingActivity(false);
      setActivityInlineError(null);
    }
  }, [activities, selectedActivityId]);

  useEffect(() => {
    if (selectedLaborId != null && !currentLabors.some((l) => l.id === selectedLaborId)) {
      setSelectedLaborId(null);
      setEditingLaborId(null);
      setIsInlineEditingLabor(false);
      setLaborInlineError(null);
    }
  }, [currentLabors, selectedLaborId]);

  // ========= ACTIVIDADES: handlers =========
  const onSelectActivityRow = (a: Activity) => {
    if (selectedActivityId === a.id) return;
    setSelectedActivityId(a.id);
    setIsInlineEditingActivity(false);
    setEditingActivityId(null);
    setActivityInlineError(null);
  };

  const startEditActivityInline = (a: Activity) => {
    setSelectedActivityId(a.id);
    setEditingActivityId(a.id);
    setIsInlineEditingActivity(true);
    setActivityInlineError(null);

    setActivityName(a.name ?? "");
    setActivityCode(a.code ?? "");
  };

  const cancelEditActivityInline = () => {
    setIsInlineEditingActivity(false);
    setEditingActivityId(null);
    setActivityInlineError(null);
  };

  const validateAndBuildActivityBody = () => {
    if (!activityName.trim()) return { ok: false as const, error: "El nombre de la actividad es obligatorio." };
    return {
      ok: true as const,
      body: {
        name: activityName.trim(),
        code: activityCode.trim() || null,
      },
    };
  };

  const saveInlineActivity = async () => {
    if (editingActivityId == null) {
      setActivityInlineError("No hay actividad en edición.");
      return;
    }
    const v = validateAndBuildActivityBody();
    if (!v.ok) {
      setActivityInlineError(v.error);
      return;
    }

    try {
      setSaving(true);
      setActivityInlineError(null);
      setError(null);

      await safeFetchJson(`${apiBaseUrl}/activities/${editingActivityId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(v.body),
      });

      setIsInlineEditingActivity(false);
      setEditingActivityId(null);
      await loadActivities();
    } catch (e: any) {
      console.error(e);
      setActivityInlineError(e?.message || "No se pudo guardar la actividad.");
    } finally {
      setSaving(false);
    }
  };

  const validateAndBuildNewActivityBody = () => {
    if (!newActivityName.trim()) return { ok: false as const, error: "El nombre de la actividad es obligatorio." };
    return {
      ok: true as const,
      body: {
        name: newActivityName.trim(),
        code: newActivityCode.trim() || null,
      },
    };
  };

  const resetNewActivityRow = () => {
    setNewActivityName("");
    setNewActivityCode("");
    setNewActivityRowError(null);
  };

  const createNewActivityFromRow = async () => {
    const v = validateAndBuildNewActivityBody();
    if (!v.ok) {
      setNewActivityRowError(v.error);
      return;
    }

    try {
      setSaving(true);
      setNewActivityRowError(null);
      setError(null);

      await safeFetchJson(`${apiBaseUrl}/activities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(v.body),
      });

      resetNewActivityRow();
      await loadActivities();
    } catch (e: any) {
      console.error(e);
      setNewActivityRowError(e?.message || "No se pudo crear la actividad.");
    } finally {
      setSaving(false);
    }
  };

  const deleteSelectedActivity = async () => {
    if (!selectedActivity) return;
    const ok = window.confirm("¿Eliminar esta actividad? Puede fallar si tiene labores asociadas.");
    if (!ok) return;

    try {
      setSaving(true);
      setError(null);

      await safeFetchJson(`${apiBaseUrl}/activities/${selectedActivity.id}`, { method: "DELETE" });

      if (selectedActivityId === selectedActivity.id) setSelectedActivityId(null);
      cancelEditActivityInline();
      await loadActivities();
      await refreshLabors();
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "No se pudo eliminar la actividad.");
    } finally {
      setSaving(false);
    }
  };

  const canAddNewActivity = Boolean(newActivityName.trim());

  // ========= LABORES: handlers =========
  const onSelectLaborRow = (l: Labor) => {
    if (selectedLaborId === l.id) return;
    setSelectedLaborId(l.id);
    setIsInlineEditingLabor(false);
    setEditingLaborId(null);
    setLaborInlineError(null);
  };

  const startEditLaborInline = (l: Labor) => {
    setSelectedLaborId(l.id);
    setEditingLaborId(l.id);
    setIsInlineEditingLabor(true);
    setLaborInlineError(null);

    setLaborActivityId(String(l.activity_id));
    setLaborName(l.name ?? "");
    setLaborCode(l.code ?? "");
    setLaborEffortFactor(l.effort_factor != null ? String(l.effort_factor) : "");
    setLaborTargetSpeed(l.target_speed_kmh != null ? String(l.target_speed_kmh) : "");
  };

  const cancelEditLaborInline = () => {
    setIsInlineEditingLabor(false);
    setEditingLaborId(null);
    setLaborInlineError(null);
  };

  const validateAndBuildLaborBody = () => {
    if (!laborName.trim()) return { ok: false as const, error: "El nombre de la labor es obligatorio." };
    if (!laborActivityId) return { ok: false as const, error: "Debes seleccionar una actividad." };

    const eff = parseNumberOrNull(laborEffortFactor);
    if (laborEffortFactor && eff == null) return { ok: false as const, error: "Factor de esfuerzo inválido." };

    const spd = parseNumberOrNull(laborTargetSpeed);
    if (laborTargetSpeed && spd == null) return { ok: false as const, error: "Velocidad objetivo inválida." };

    return {
      ok: true as const,
      body: {
        activity_id: Number(laborActivityId),
        name: laborName.trim(),
        code: laborCode.trim() || null,
        effort_factor: eff,
        target_speed_kmh: spd,
      },
    };
  };

  const saveInlineLabor = async () => {
    if (editingLaborId == null) {
      setLaborInlineError("No hay labor en edición.");
      return;
    }
    const v = validateAndBuildLaborBody();
    if (!v.ok) {
      setLaborInlineError(v.error);
      return;
    }

    try {
      setSaving(true);
      setLaborInlineError(null);
      setError(null);

      await safeFetchJson(`${apiBaseUrl}/labors/${editingLaborId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(v.body),
      });

      cancelEditLaborInline();
      await refreshLabors();
    } catch (e: any) {
      console.error(e);
      setLaborInlineError(e?.message || "No se pudo guardar la labor.");
    } finally {
      setSaving(false);
    }
  };

  const validateAndBuildNewLaborBody = () => {
    if (!newLaborName.trim()) return { ok: false as const, error: "El nombre de la labor es obligatorio." };
    if (!newLaborActivityId) return { ok: false as const, error: "Debes seleccionar una actividad." };

    const eff = parseNumberOrNull(newLaborEffortFactor);
    if (newLaborEffortFactor && eff == null) return { ok: false as const, error: "Factor de esfuerzo inválido." };

    const spd = parseNumberOrNull(newLaborTargetSpeed);
    if (newLaborTargetSpeed && spd == null) return { ok: false as const, error: "Velocidad objetivo inválida." };

    return {
      ok: true as const,
      body: {
        activity_id: Number(newLaborActivityId),
        name: newLaborName.trim(),
        code: newLaborCode.trim() || null,
        effort_factor: eff,
        target_speed_kmh: spd,
      },
    };
  };

  const resetNewLaborRow = () => {
    setNewLaborActivityId("");
    setNewLaborName("");
    setNewLaborCode("");
    setNewLaborEffortFactor("");
    setNewLaborTargetSpeed("");
    setNewLaborRowError(null);
  };

  const createNewLaborFromRow = async () => {
    const v = validateAndBuildNewLaborBody();
    if (!v.ok) {
      setNewLaborRowError(v.error);
      return;
    }

    try {
      setSaving(true);
      setNewLaborRowError(null);
      setError(null);

      await safeFetchJson(`${apiBaseUrl}/labors`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(v.body),
      });

      resetNewLaborRow();
      await refreshLabors();
    } catch (e: any) {
      console.error(e);
      setNewLaborRowError(e?.message || "No se pudo crear la labor.");
    } finally {
      setSaving(false);
    }
  };

  const deleteSelectedLabor = async () => {
    if (!selectedLabor) return;
    const ok = window.confirm("¿Eliminar esta labor? Esta acción no se puede deshacer.");
    if (!ok) return;

    try {
      setSaving(true);
      setError(null);

      await safeFetchJson(`${apiBaseUrl}/labors/${selectedLabor.id}`, { method: "DELETE" });

      if (selectedLaborId === selectedLabor.id) setSelectedLaborId(null);
      cancelEditLaborInline();
      await refreshLabors();
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "No se pudo eliminar la labor.");
    } finally {
      setSaving(false);
    }
  };

  const canAddNewLabor = Boolean(newLaborName.trim() && newLaborActivityId);

  return (
    <section className="card entity-page">
      {/* Global error */}
      {error && <div className="tracker-error">⚠️ {error}</div>}

      {/* ============ ACTIVIDADES ============ */}
      <section className="card" style={{ marginTop: 0 }}>
        <div className="card-header">
          <div>
            <div className="card-title">Actividades</div>
            <div className="card-subtitle">Catálogo de actividades (padre de las labores).</div>
          </div>
        </div>

        <div className="entity-table-wrapper">
          {loading ? (
            <div className="sessions-loading">Cargando…</div>
          ) : activities.length === 0 ? (
            <div className="sessions-empty">Sin actividades. Agrega una en la última fila.</div>
          ) : (
            <table className="entity-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Nombre</th>
                  <th>Código</th>
                </tr>
              </thead>

              <tbody>
                {activities.map((a) => {
                  const isSelected = selectedActivityId === a.id;
                  const isEditingThisRow = isInlineEditingActivity && editingActivityId === a.id && isSelected;

                  return (
                    <tr
                      key={a.id}
                      onClick={() => onSelectActivityRow(a)}
                      style={{
                        cursor: "pointer",
                        background: isSelected ? "rgba(0,0,0,0.04)" : undefined,
                      }}
                    >
                      <td>{a.id}</td>

                      <td>
                        {isEditingThisRow ? (
                          <input className="form-input" value={activityName} onChange={(e) => setActivityName(e.target.value)} />
                        ) : (
                          a.name
                        )}
                      </td>

                      <td>
                        {isEditingThisRow ? (
                          <input className="form-input" value={activityCode} onChange={(e) => setActivityCode(e.target.value)} placeholder="Opcional" />
                        ) : (
                          a.code || "—"
                        )}
                      </td>
                    </tr>
                  );
                })}

                {/* NEW ROW */}
                <tr style={{ background: "rgba(0,0,0,0.02)" }}>
                  <td style={{ fontWeight: 700 }}>+</td>

                  <td>
                    <input
                      className="form-input"
                      value={newActivityName}
                      onChange={(e) => setNewActivityName(e.target.value)}
                      placeholder="Nueva actividad"
                    />
                  </td>

                  <td>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      <input
                        className="form-input"
                        value={newActivityCode}
                        onChange={(e) => setNewActivityCode(e.target.value)}
                        placeholder="Código (opcional)"
                      />

                      {canAddNewActivity && (
                        <button type="button" className="form-button-primary" onClick={() => void createNewActivityFromRow()} disabled={saving}>
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
            {selectedActivity ? (
              <>
                Seleccionado: <b>#{selectedActivity.id}</b> — {selectedActivity.name}
              </>
            ) : (
              "Selecciona una actividad para editar / borrar."
            )}
          </div>

          {activityInlineError && <div className="tracker-error">⚠️ {activityInlineError}</div>}
          {newActivityRowError && <div className="tracker-error">⚠️ {newActivityRowError}</div>}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {!isInlineEditingActivity ? (
              <button
                type="button"
                className="form-button-primary"
                disabled={!selectedActivity}
                onClick={() => selectedActivity && startEditActivityInline(selectedActivity)}
              >
                Editar
              </button>
            ) : (
              <>
                <button type="button" className="form-button-primary" onClick={() => void saveInlineActivity()} disabled={saving}>
                  {saving ? "Guardando..." : "Guardar cambios"}
                </button>

                <button type="button" className="form-button-primary" onClick={cancelEditActivityInline} disabled={saving}>
                  Cancelar
                </button>
              </>
            )}

            <button type="button" className="form-button-primary" disabled={!selectedActivity || saving} onClick={() => void deleteSelectedActivity()}>
              Borrar
            </button>
          </div>
        </div>
      </section>

      {/* ============ LABORES ============ */}
      <section className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <div>
            <div className="card-title">Labores</div>
            <div className="card-subtitle">Catálogo de labores (hijas de una actividad). Usa el filtro para listar.</div>
          </div>
        </div>

        {/* filtro */}
        <div className="form-grid" style={{ marginTop: 8 }}>
          <div className="form-field">
            <label className="form-label">Filtrar por actividad</label>
            <select className="form-select" value={filterLaborsActivityId} onChange={(e) => setFilterLaborsActivityId(e.target.value)}>
              <option value="">Todas</option>
              {activities.map((a) => (
                <option key={a.id} value={String(a.id)}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="entity-table-wrapper">
          {loading ? (
            <div className="sessions-loading">Cargando…</div>
          ) : currentLabors.length === 0 ? (
            <div className="sessions-empty">Sin labores para el criterio. Agrega una en la última fila.</div>
          ) : (
            <table className="entity-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Actividad</th>
                  <th>Labor</th>
                  <th>Código</th>
                  <th>Factor</th>
                  <th>Vel. objetivo</th>
                </tr>
              </thead>

              <tbody>
                {currentLabors.map((l) => {
                  const isSelected = selectedLaborId === l.id;
                  const isEditingThisRow = isInlineEditingLabor && editingLaborId === l.id && isSelected;

                  return (
                    <Fragment key={l.id}>
                      <tr
                        onClick={() => onSelectLaborRow(l)}
                        style={{
                          cursor: "pointer",
                          background: isSelected ? "rgba(0,0,0,0.04)" : undefined,
                        }}
                      >
                        <td>{l.id}</td>

                        <td>
                          {isEditingThisRow ? (
                            <select className="form-input" value={laborActivityId} onChange={(e) => setLaborActivityId(e.target.value)}>
                              <option value="">Selecciona…</option>
                              {activities.map((a) => (
                                <option key={a.id} value={String(a.id)}>
                                  {a.name}
                                </option>
                              ))}
                            </select>
                          ) : (
                            getActivityName(l.activity_id)
                          )}
                        </td>

                        <td>
                          {isEditingThisRow ? (
                            <input className="form-input" value={laborName} onChange={(e) => setLaborName(e.target.value)} placeholder="Nombre labor" />
                          ) : (
                            l.name
                          )}
                        </td>

                        <td>
                          {isEditingThisRow ? (
                            <input className="form-input" value={laborCode} onChange={(e) => setLaborCode(e.target.value)} placeholder="Opcional" />
                          ) : (
                            l.code || "—"
                          )}
                        </td>

                        <td>
                          {isEditingThisRow ? (
                            <input
                              className="form-input"
                              type="number"
                              min={0}
                              step="0.01"
                              value={laborEffortFactor}
                              onChange={(e) => setLaborEffortFactor(e.target.value)}
                              placeholder="Ej: 1.30"
                            />
                          ) : l.effort_factor != null ? (
                            String(l.effort_factor).replace(".", ",")
                          ) : (
                            "—"
                          )}
                        </td>

                        <td>
                          {isEditingThisRow ? (
                            <input
                              className="form-input"
                              type="number"
                              min={0}
                              step="0.1"
                              value={laborTargetSpeed}
                              onChange={(e) => setLaborTargetSpeed(e.target.value)}
                              placeholder="Ej: 6.0"
                            />
                          ) : l.target_speed_kmh != null ? (
                            String(l.target_speed_kmh).replace(".", ",")
                          ) : (
                            "—"
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
                    <select className="form-input" value={newLaborActivityId} onChange={(e) => setNewLaborActivityId(e.target.value)}>
                      <option value="">Selecciona…</option>
                      {activities.map((a) => (
                        <option key={a.id} value={String(a.id)}>
                          {a.name}
                        </option>
                      ))}
                    </select>
                  </td>

                  <td>
                    <input
                      className="form-input"
                      value={newLaborName}
                      onChange={(e) => setNewLaborName(e.target.value)}
                      placeholder="Nueva labor"
                    />
                  </td>

                  <td>
                    <input
                      className="form-input"
                      value={newLaborCode}
                      onChange={(e) => setNewLaborCode(e.target.value)}
                      placeholder="Código (opcional)"
                    />
                  </td>

                  <td>
                    <input
                      className="form-input"
                      type="number"
                      min={0}
                      step="0.01"
                      value={newLaborEffortFactor}
                      onChange={(e) => setNewLaborEffortFactor(e.target.value)}
                      placeholder="Ej: 1.30"
                    />
                  </td>

                  <td>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      <input
                        className="form-input"
                        type="number"
                        min={0}
                        step="0.1"
                        value={newLaborTargetSpeed}
                        onChange={(e) => setNewLaborTargetSpeed(e.target.value)}
                        placeholder="Ej: 6.0"
                      />

                      {canAddNewLabor && (
                        <button type="button" className="form-button-primary" onClick={() => void createNewLaborFromRow()} disabled={saving}>
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
            {selectedLabor ? (
              <>
                Seleccionado: <b>#{selectedLabor.id}</b> — {selectedLabor.name}
              </>
            ) : (
              "Selecciona una labor para editar / borrar."
            )}
          </div>

          {laborInlineError && <div className="tracker-error">⚠️ {laborInlineError}</div>}
          {newLaborRowError && <div className="tracker-error">⚠️ {newLaborRowError}</div>}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {!isInlineEditingLabor ? (
              <button
                type="button"
                className="form-button-primary"
                disabled={!selectedLabor}
                onClick={() => selectedLabor && startEditLaborInline(selectedLabor)}
              >
                Editar
              </button>
            ) : (
              <>
                <button type="button" className="form-button-primary" onClick={() => void saveInlineLabor()} disabled={saving}>
                  {saving ? "Guardando..." : "Guardar cambios"}
                </button>

                <button type="button" className="form-button-primary" onClick={cancelEditLaborInline} disabled={saving}>
                  Cancelar
                </button>
              </>
            )}

            <button type="button" className="form-button-primary" disabled={!selectedLabor || saving} onClick={() => void deleteSelectedLabor()}>
              Borrar
            </button>
          </div>
        </div>
      </section>
    </section>
  );
}
