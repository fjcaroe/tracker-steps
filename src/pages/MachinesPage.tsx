// src/pages/MachinesPage.tsx
/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useState, Fragment } from "react";

type FuelUnit = "lph" | "kmpl";

type Machine = {
  id: number;
  name: string;
  plate?: string | null;
  description?: string | null;
  cost_center_id?: number | null;
  tank_capacity_liters?: number | null;

  fuel_consumption_unit?: FuelUnit | null;
  fuel_consumption_lph?: number | null;
  fuel_efficiency_kmpl?: number | null;

  default_activity_id?: number | null;
  default_labor_id?: number | null;
};

type CostCenter = { id: number; name: string };
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

// ✅ robusto: soporta 204 o body vacío (útil para DELETE si algún día devuelves 204)
async function safeFetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const text = await res.text();

  if (!res.ok) {
    throw new Error(`Error ${res.status}: ${text}`);
  }

  if (!text) return undefined as unknown as T;

  try {
    return JSON.parse(text) as T;
  } catch {
    // por si el backend devuelve texto plano
    return text as unknown as T;
  }
}

const MachinesPage = () => {
  // tablas
  const [machines, setMachines] = useState<Machine[]>([]);
  const [costCenters, setCostCenters] = useState<CostCenter[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [laborsAll, setLaborsAll] = useState<Labor[]>([]);

  // estados generales
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // selección + edición inline
  const [selectedMachineId, setSelectedMachineId] = useState<number | null>(null);
  const [editingMachineId, setEditingMachineId] = useState<number | null>(null);
  const [isInlineEditing, setIsInlineEditing] = useState(false);

  // edición inline fields
  const [mName, setMName] = useState("");
  const [mPlate, setMPlate] = useState("");
  const [mDescription, setMDescription] = useState("");
  const [mCostCenterId, setMCostCenterId] = useState<string>("");
  const [mTankCapacity, setMTankCapacity] = useState<string>("");

  const [mFuelUnit, setMFuelUnit] = useState<FuelUnit>("lph");
  const [mFuelPerHour, setMFuelPerHour] = useState<string>("");
  const [mFuelKmPerLt, setMFuelKmPerLt] = useState<string>("");

  const [mDefaultActivityId, setMDefaultActivityId] = useState<string>("");
  const [mDefaultLaborId, setMDefaultLaborId] = useState<string>("");

  const [saveError, setSaveError] = useState<string | null>(null);

  // new row (create)
  const [newName, setNewName] = useState("");
  const [newPlate, setNewPlate] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newCostCenterId, setNewCostCenterId] = useState<string>("");
  const [newTankCapacity, setNewTankCapacity] = useState<string>("");

  const [newFuelUnit, setNewFuelUnit] = useState<FuelUnit>("lph");
  const [newFuelPerHour, setNewFuelPerHour] = useState<string>("");
  const [newFuelKmPerLt, setNewFuelKmPerLt] = useState<string>("");

  const [newDefaultActivityId, setNewDefaultActivityId] = useState<string>("");
  const [newDefaultLaborId, setNewDefaultLaborId] = useState<string>("");

  const [newRowError, setNewRowError] = useState<string | null>(null);

  // ---------- loaders ----------
  const loadMachines = async () => {
    try {
      setLoading(true);
      setError(null);
      setMachines(await safeFetchJson<Machine[]>(`${apiBaseUrl}/machines`));
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "No se pudieron cargar las máquinas.");
    } finally {
      setLoading(false);
    }
  };

  const loadCostCenters = async () => {
    try {
      setCostCenters(await safeFetchJson<CostCenter[]>(`${apiBaseUrl}/cost_centers`));
    } catch (e) {
      console.error("Error cargando centros de costo", e);
    }
  };

  const loadActivities = async () => {
    try {
      setActivities(await safeFetchJson<Activity[]>(`${apiBaseUrl}/activities`));
    } catch (e) {
      console.error("Error cargando actividades", e);
    }
  };

  const loadLaborsAll = async () => {
    try {
      setLaborsAll(await safeFetchJson<Labor[]>(`${apiBaseUrl}/labors`));
    } catch (e) {
      console.error("Error cargando labores", e);
    }
  };

  useEffect(() => {
    void loadMachines();
    void loadCostCenters();
    void loadActivities();
    void loadLaborsAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---------- maps/helpers ----------
  const costCenterById = useMemo(() => new Map(costCenters.map((c) => [c.id, c])), [costCenters]);
  const activityById = useMemo(() => new Map(activities.map((a) => [a.id, a])), [activities]);
  const laborById = useMemo(() => new Map(laborsAll.map((l) => [l.id, l])), [laborsAll]);

  const selectedMachine = useMemo(
    () => machines.find((m) => m.id === selectedMachineId) ?? null,
    [machines, selectedMachineId]
  );

  useEffect(() => {
    // si el seleccionado ya no existe, limpiar selección/edición
    if (selectedMachineId != null && !machines.some((m) => m.id === selectedMachineId)) {
      setSelectedMachineId(null);
      setEditingMachineId(null);
      setIsInlineEditing(false);
      setSaveError(null);
    }
  }, [machines, selectedMachineId]);

  const parseNumberOrNull = (value: string): number | null => {
    if (!value.trim()) return null;
    const parsed = parseFloat(value.replace(",", "."));
    return Number.isNaN(parsed) ? null : parsed;
  };

  const formatNumber = (n?: number | null, decs = 2) => {
    if (n == null) return "—";
    return n.toFixed(decs).replace(".", ",");
  };

  const getCostCenterName = (id?: number | null) => {
    if (!id) return "—";
    return costCenterById.get(id)?.name || `ID ${id}`;
  };

  const getActivityName = (id?: number | null) => {
    if (!id) return "—";
    return activityById.get(id)?.name || `ID ${id}`;
  };

  const getLaborName = (id?: number | null) => {
    if (!id) return "—";
    return laborById.get(id)?.name || `ID ${id}`;
  };

  const resetEdit = () => {
    setEditingMachineId(null);
    setIsInlineEditing(false);
    setMName("");
    setMPlate("");
    setMDescription("");
    setMCostCenterId("");
    setMTankCapacity("");
    setMFuelUnit("lph");
    setMFuelPerHour("");
    setMFuelKmPerLt("");
    setMDefaultActivityId("");
    setMDefaultLaborId("");
    setSaveError(null);
  };

  const resetNewRow = () => {
    setNewName("");
    setNewPlate("");
    setNewDescription("");
    setNewCostCenterId("");
    setNewTankCapacity("");
    setNewFuelUnit("lph");
    setNewFuelPerHour("");
    setNewFuelKmPerLt("");
    setNewDefaultActivityId("");
    setNewDefaultLaborId("");
    setNewRowError(null);
  };

  const onSelectRow = (m: Machine) => {
    if (selectedMachineId === m.id) return; // evita cortar edición al clickear inputs
    setSelectedMachineId(m.id);
    setIsInlineEditing(false);
    setEditingMachineId(null);
    setSaveError(null);
  };

  const startEditMachine = (m: Machine) => {
    setSelectedMachineId(m.id);
    setEditingMachineId(m.id);
    setIsInlineEditing(true);
    setSaveError(null);

    setMName(m.name ?? "");
    setMPlate(m.plate ?? "");
    setMDescription(m.description ?? "");
    setMCostCenterId(m.cost_center_id != null ? String(m.cost_center_id) : "");
    setMTankCapacity(m.tank_capacity_liters != null ? String(m.tank_capacity_liters) : "");

    const unit = (m.fuel_consumption_unit as FuelUnit) || "lph";
    setMFuelUnit(unit);
    setMFuelPerHour(unit === "lph" && m.fuel_consumption_lph != null ? String(m.fuel_consumption_lph) : "");
    setMFuelKmPerLt(unit === "kmpl" && m.fuel_efficiency_kmpl != null ? String(m.fuel_efficiency_kmpl) : "");

    setMDefaultActivityId(m.default_activity_id != null ? String(m.default_activity_id) : "");
    setMDefaultLaborId(m.default_labor_id != null ? String(m.default_labor_id) : "");
  };

  const laborsForEdit = useMemo(() => {
    const aId = mDefaultActivityId ? Number(mDefaultActivityId) : null;
    if (!aId) return [];
    return laborsAll.filter((l) => l.activity_id === aId);
  }, [mDefaultActivityId, laborsAll]);

  const laborsForNew = useMemo(() => {
    const aId = newDefaultActivityId ? Number(newDefaultActivityId) : null;
    if (!aId) return [];
    return laborsAll.filter((l) => l.activity_id === aId);
  }, [newDefaultActivityId, laborsAll]);

  // ---------- validate/build bodies ----------
  const buildBodyFromEdit = () => {
    if (!mName.trim()) return { ok: false as const, error: "El nombre de la máquina es obligatorio." };

    const tank = parseNumberOrNull(mTankCapacity);
    if (mTankCapacity.trim() && tank == null) return { ok: false as const, error: "Capacidad de estanque inválida." };

    const lph = mFuelUnit === "lph" ? parseNumberOrNull(mFuelPerHour) : null;
    if (mFuelUnit === "lph" && mFuelPerHour.trim() && lph == null) return { ok: false as const, error: "Consumo (L/h) inválido." };

    const kmpl = mFuelUnit === "kmpl" ? parseNumberOrNull(mFuelKmPerLt) : null;
    if (mFuelUnit === "kmpl" && mFuelKmPerLt.trim() && kmpl == null) return { ok: false as const, error: "Rendimiento (km/L) inválido." };

    const body: any = {
      name: mName.trim(),
      plate: mPlate.trim() || null,
      description: mDescription.trim() || null,
      cost_center_id: mCostCenterId ? Number(mCostCenterId) : null,
      tank_capacity_liters: tank,

      fuel_consumption_unit: mFuelUnit,
      fuel_consumption_lph: mFuelUnit === "lph" ? lph : null,
      fuel_efficiency_kmpl: mFuelUnit === "kmpl" ? kmpl : null,

      default_activity_id: mDefaultActivityId ? Number(mDefaultActivityId) : null,
      default_labor_id: mDefaultLaborId ? Number(mDefaultLaborId) : null,
    };

    return { ok: true as const, body };
  };

  const buildBodyFromNew = () => {
    if (!newName.trim()) return { ok: false as const, error: "El nombre de la máquina es obligatorio." };

    const tank = parseNumberOrNull(newTankCapacity);
    if (newTankCapacity.trim() && tank == null) return { ok: false as const, error: "Capacidad de estanque inválida." };

    const lph = newFuelUnit === "lph" ? parseNumberOrNull(newFuelPerHour) : null;
    if (newFuelUnit === "lph" && newFuelPerHour.trim() && lph == null) return { ok: false as const, error: "Consumo (L/h) inválido." };

    const kmpl = newFuelUnit === "kmpl" ? parseNumberOrNull(newFuelKmPerLt) : null;
    if (newFuelUnit === "kmpl" && newFuelKmPerLt.trim() && kmpl == null) return { ok: false as const, error: "Rendimiento (km/L) inválido." };

    const body: any = {
      name: newName.trim(),
      plate: newPlate.trim() || null,
      description: newDescription.trim() || null,
      cost_center_id: newCostCenterId ? Number(newCostCenterId) : null,
      tank_capacity_liters: tank,

      fuel_consumption_unit: newFuelUnit,
      fuel_consumption_lph: newFuelUnit === "lph" ? lph : null,
      fuel_efficiency_kmpl: newFuelUnit === "kmpl" ? kmpl : null,

      default_activity_id: newDefaultActivityId ? Number(newDefaultActivityId) : null,
      default_labor_id: newDefaultLaborId ? Number(newDefaultLaborId) : null,
    };

    return { ok: true as const, body };
  };

  // ---------- actions ----------
  const saveInlineMachine = async () => {
    if (editingMachineId == null) {
      setSaveError("No hay máquina en edición.");
      return;
    }

    const v = buildBodyFromEdit();
    if (!v.ok) {
      setSaveError(v.error);
      return;
    }

    try {
      setSaving(true);
      setSaveError(null);
      setError(null);

      await safeFetchJson(`${apiBaseUrl}/machines/${editingMachineId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(v.body),
      });

      resetEdit();
      await loadMachines();
    } catch (e: any) {
      console.error(e);
      setSaveError(e?.message || "No se pudo guardar la máquina.");
    } finally {
      setSaving(false);
    }
  };

  const createNewMachineFromRow = async () => {
    const v = buildBodyFromNew();
    if (!v.ok) {
      setNewRowError(v.error);
      return;
    }

    try {
      setSaving(true);
      setNewRowError(null);
      setError(null);

      await safeFetchJson(`${apiBaseUrl}/machines`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(v.body),
      });

      resetNewRow();
      await loadMachines();
    } catch (e: any) {
      console.error(e);
      setNewRowError(e?.message || "No se pudo crear la máquina.");
    } finally {
      setSaving(false);
    }
  };

  // ✅ DELETE /machines/{id}
  const deleteSelectedMachine = async () => {
    if (!selectedMachine) return;

    const ok = window.confirm(`¿Eliminar la máquina #${selectedMachine.id} (${selectedMachine.name})?`);
    if (!ok) return;

    try {
      setDeleting(true);
      setError(null);
      setSaveError(null);

      await safeFetchJson(`${apiBaseUrl}/machines/${selectedMachine.id}`, {
        method: "DELETE",
      });

      // limpiar selección/edición
      resetEdit();
      setSelectedMachineId(null);

      await loadMachines();
    } catch (e: any) {
      console.error(e);
      // tu backend devuelve 409 si hay relaciones, lo mostramos tal cual
      setError(e?.message || "No se pudo eliminar la máquina.");
    } finally {
      setDeleting(false);
    }
  };

  const canAddNew = Boolean(newName.trim());

  return (
    <section className="card entity-page">
      <div className="card-header">
        <div>
          <div className="card-title">Máquinas</div>
          <div className="card-subtitle">Registro de tractores/equipos. Edita inline y agrega en la última fila.</div>
        </div>
      </div>

      {error && <div className="tracker-error">⚠️ {error}</div>}

      <div className="entity-table-wrapper">
        {loading ? (
          <div className="sessions-loading">Cargando máquinas…</div>
        ) : machines.length === 0 ? (
          <div className="sessions-empty">No hay máquinas registradas. Agrega la primera en la última fila.</div>
        ) : (
          <table className="entity-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Nombre</th>
                <th>Patente / Código</th>
                <th>Centro de costo</th>
                <th>Estanque (L)</th>
                <th>Medida</th>
                <th>Consumo</th>
                <th>Actividad def.</th>
                <th>Labor def.</th>
                <th>Descripción</th>
              </tr>
            </thead>

            <tbody>
              {machines.map((m) => {
                const isSelected = selectedMachineId === m.id;
                const isEditingThisRow = isInlineEditing && editingMachineId === m.id && isSelected;
                const unit = (m.fuel_consumption_unit || "lph") as FuelUnit;

                return (
                  <Fragment key={m.id}>
                    <tr
                      onClick={() => onSelectRow(m)}
                      style={{ cursor: "pointer", background: isSelected ? "rgba(0,0,0,0.04)" : undefined }}
                      title="Click para seleccionar"
                    >
                      <td>{m.id}</td>

                      <td>
                        {isEditingThisRow ? (
                          <input className="form-input" value={mName} onChange={(e) => setMName(e.target.value)} placeholder="Nombre máquina" />
                        ) : (
                          m.name
                        )}
                      </td>

                      <td>
                        {isEditingThisRow ? (
                          <input className="form-input" value={mPlate} onChange={(e) => setMPlate(e.target.value)} placeholder="Patente / Código" />
                        ) : (
                          m.plate || "—"
                        )}
                      </td>

                      <td>
                        {isEditingThisRow ? (
                          <select className="form-select" value={mCostCenterId} onChange={(e) => setMCostCenterId(e.target.value)}>
                            <option value="">Sin centro de costo</option>
                            {costCenters.map((c) => (
                              <option key={c.id} value={String(c.id)}>
                                {c.name}
                              </option>
                            ))}
                          </select>
                        ) : (
                          getCostCenterName(m.cost_center_id)
                        )}
                      </td>

                      <td>
                        {isEditingThisRow ? (
                          <input
                            className="form-input"
                            type="number"
                            min={0}
                            step="0.1"
                            value={mTankCapacity}
                            onChange={(e) => setMTankCapacity(e.target.value)}
                            placeholder="Ej: 220"
                          />
                        ) : (
                          formatNumber(m.tank_capacity_liters)
                        )}
                      </td>

                      <td>
                        {isEditingThisRow ? (
                          <select
                            className="form-select"
                            value={mFuelUnit}
                            onChange={(e) => {
                              const next = e.target.value as FuelUnit;
                              setMFuelUnit(next);
                              if (next === "lph") setMFuelKmPerLt("");
                              else setMFuelPerHour("");
                            }}
                          >
                            <option value="lph">L/h</option>
                            <option value="kmpl">km/L</option>
                          </select>
                        ) : (
                          unit === "kmpl" ? "km/L" : "L/h"
                        )}
                      </td>

                      <td>
                        {isEditingThisRow ? (
                          mFuelUnit === "lph" ? (
                            <input
                              className="form-input"
                              type="number"
                              min={0}
                              step="0.1"
                              value={mFuelPerHour}
                              onChange={(e) => setMFuelPerHour(e.target.value)}
                              placeholder="Ej: 12.5"
                            />
                          ) : (
                            <input
                              className="form-input"
                              type="number"
                              min={0}
                              step="0.01"
                              value={mFuelKmPerLt}
                              onChange={(e) => setMFuelKmPerLt(e.target.value)}
                              placeholder="Ej: 3.25"
                            />
                          )
                        ) : unit === "kmpl" ? (
                          formatNumber(m.fuel_efficiency_kmpl, 3)
                        ) : (
                          formatNumber(m.fuel_consumption_lph)
                        )}
                      </td>

                      <td>
                        {isEditingThisRow ? (
                          <select
                            className="form-select"
                            value={mDefaultActivityId}
                            onChange={(e) => {
                              const next = e.target.value;
                              setMDefaultActivityId(next);
                              setMDefaultLaborId("");
                            }}
                          >
                            <option value="">—</option>
                            {activities.map((a) => (
                              <option key={a.id} value={String(a.id)}>
                                {a.name}
                              </option>
                            ))}
                          </select>
                        ) : (
                          getActivityName(m.default_activity_id)
                        )}
                      </td>

                      <td>
                        {isEditingThisRow ? (
                          <select
                            className="form-select"
                            value={mDefaultLaborId}
                            onChange={(e) => setMDefaultLaborId(e.target.value)}
                            disabled={!mDefaultActivityId}
                          >
                            <option value="">{mDefaultActivityId ? "Selecciona…" : "—"}</option>
                            {laborsForEdit.map((l) => (
                              <option key={l.id} value={String(l.id)}>
                                {l.name}
                              </option>
                            ))}
                          </select>
                        ) : (
                          getLaborName(m.default_labor_id)
                        )}
                      </td>

                      <td style={{ minWidth: 220 }}>
                        {isEditingThisRow ? (
                          <input className="form-input" value={mDescription} onChange={(e) => setMDescription(e.target.value)} placeholder="Descripción" />
                        ) : (
                          m.description || "—"
                        )}
                      </td>
                    </tr>
                  </Fragment>
                );
              })}

              {/* ===== NEW ROW (inline create) ===== */}
              <tr style={{ background: "rgba(0,0,0,0.02)" }}>
                <td style={{ fontWeight: 700 }}>+</td>

                <td>
                  <input className="form-input" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Nueva máquina" />
                </td>

                <td>
                  <input className="form-input" value={newPlate} onChange={(e) => setNewPlate(e.target.value)} placeholder="Patente / Código" />
                </td>

                <td>
                  <select className="form-select" value={newCostCenterId} onChange={(e) => setNewCostCenterId(e.target.value)}>
                    <option value="">Sin centro de costo</option>
                    {costCenters.map((c) => (
                      <option key={c.id} value={String(c.id)}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </td>

                <td>
                  <input className="form-input" type="number" min={0} step="0.1" value={newTankCapacity} onChange={(e) => setNewTankCapacity(e.target.value)} placeholder="Ej: 220" />
                </td>

                <td>
                  <select
                    className="form-select"
                    value={newFuelUnit}
                    onChange={(e) => {
                      const next = e.target.value as FuelUnit;
                      setNewFuelUnit(next);
                      if (next === "lph") setNewFuelKmPerLt("");
                      else setNewFuelPerHour("");
                    }}
                  >
                    <option value="lph">L/h</option>
                    <option value="kmpl">km/L</option>
                  </select>
                </td>

                <td>
                  {newFuelUnit === "lph" ? (
                    <input className="form-input" type="number" min={0} step="0.1" value={newFuelPerHour} onChange={(e) => setNewFuelPerHour(e.target.value)} placeholder="Ej: 12.5" />
                  ) : (
                    <input className="form-input" type="number" min={0} step="0.01" value={newFuelKmPerLt} onChange={(e) => setNewFuelKmPerLt(e.target.value)} placeholder="Ej: 3.25" />
                  )}
                </td>

                <td>
                  <select
                    className="form-select"
                    value={newDefaultActivityId}
                    onChange={(e) => {
                      const next = e.target.value;
                      setNewDefaultActivityId(next);
                      setNewDefaultLaborId("");
                    }}
                  >
                    <option value="">—</option>
                    {activities.map((a) => (
                      <option key={a.id} value={String(a.id)}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                </td>

                <td>
                  <select className="form-select" value={newDefaultLaborId} onChange={(e) => setNewDefaultLaborId(e.target.value)} disabled={!newDefaultActivityId}>
                    <option value="">{newDefaultActivityId ? "Selecciona…" : "—"}</option>
                    {laborsForNew.map((l) => (
                      <option key={l.id} value={String(l.id)}>
                        {l.name}
                      </option>
                    ))}
                  </select>
                </td>

                <td>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <input className="form-input" value={newDescription} onChange={(e) => setNewDescription(e.target.value)} placeholder="Descripción" />

                    {canAddNew && (
                      <button type="button" className="form-button-primary" onClick={() => void createNewMachineFromRow()} disabled={saving || deleting}>
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

      {/* ===== Buttons below table (selected-based) ===== */}
      <div style={{ marginTop: 10 }}>
        <div className="card-subtitle" style={{ marginBottom: 8 }}>
          {selectedMachine ? (
            <>
              Seleccionado: <b>#{selectedMachine.id}</b> — {selectedMachine.name}
            </>
          ) : (
            "Selecciona una máquina para editar."
          )}
        </div>

        {saveError && <div className="tracker-error">⚠️ {saveError}</div>}
        {newRowError && <div className="tracker-error">⚠️ {newRowError}</div>}

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {!isInlineEditing ? (
            <>
              <button
                type="button"
                className="form-button-primary"
                disabled={!selectedMachine || saving || deleting}
                onClick={() => selectedMachine && startEditMachine(selectedMachine)}
              >
                Editar
              </button>

              <button
                type="button"
                className="form-button-secondary"
                disabled={!selectedMachine || saving || deleting}
                onClick={() => void deleteSelectedMachine()}
                title="Eliminar máquina"
              >
                {deleting ? "Eliminando..." : "Eliminar"}
              </button>
            </>
          ) : (
            <>
              <button type="button" className="form-button-primary" onClick={() => void saveInlineMachine()} disabled={saving || deleting}>
                {saving ? "Guardando..." : "Guardar cambios"}
              </button>

              <button type="button" className="form-button-primary" onClick={resetEdit} disabled={saving || deleting}>
                Cancelar
              </button>
            </>
          )}
        </div>
      </div>
    </section>
  );
};

export default MachinesPage;
