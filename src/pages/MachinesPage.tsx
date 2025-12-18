/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from "react";

type Machine = {
  id: number;
  name: string;
  plate?: string | null;
  description?: string | null;
  cost_center_id?: number | null;
  tank_capacity_liters?: number | null;
  fuel_consumption_lph?: number | null;
  fuel_consumption_lpkm?: number | null;
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
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) || "http://localhost:8000")
    .replace(/\/+$/, "");

const MachinesPage = () => {
  // tablas
  const [machines, setMachines] = useState<Machine[]>([]);
  const [costCenters, setCostCenters] = useState<CostCenter[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [labors, setLabors] = useState<Labor[]>([]);
  const [laborsByActivity, setLaborsByActivity] = useState<Labor[]>([]);
  const [newLaborEffortFactor, setNewLaborEffortFactor] = useState("");
  const [newLaborTargetSpeed, setNewLaborTargetSpeed] = useState("");
// edición actividades
const [editingActivityId, setEditingActivityId] = useState<number | null>(null);
const isEditingActivity = editingActivityId !== null;

// edición labores
const [editingLaborId, setEditingLaborId] = useState<number | null>(null);
const isEditingLabor = editingLaborId !== null;

  // estados generales
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // form máquina
  const [name, setName] = useState("");
  const [plate, setPlate] = useState("");
  const [description, setDescription] = useState("");
  const [costCenterId, setCostCenterId] = useState<string>("");

  const [tankCapacity, setTankCapacity] = useState<string>("");
  const [fuelPerHour, setFuelPerHour] = useState<string>("");
  const [fuelPerKm, setFuelPerKm] = useState<string>("");

  const [defaultActivityId, setDefaultActivityId] = useState<string>("");
  const [defaultLaborId, setDefaultLaborId] = useState<string>("");

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [editingMachineId, setEditingMachineId] = useState<number | null>(null);
  const isEditing = editingMachineId !== null;

  // maestros: crear actividad/labor
  const [newActivityName, setNewActivityName] = useState("");
  const [newActivityCode, setNewActivityCode] = useState("");
  const [newLaborName, setNewLaborName] = useState("");
  const [newLaborCode, setNewLaborCode] = useState("");
  const [newLaborActivityId, setNewLaborActivityId] = useState<string>("");
const resetActivityForm = () => {
  setNewActivityName("");
  setNewActivityCode("");
  setEditingActivityId(null);
};

const resetLaborForm = () => {
  setNewLaborActivityId("");
  setNewLaborName("");
  setNewLaborCode("");
  setNewLaborEffortFactor("");
  setNewLaborTargetSpeed("");
  setEditingLaborId(null);
};
const handleSelectActivity = (a: Activity) => {
  setEditingActivityId(a.id);
  setNewActivityName(a.name || "");
  setNewActivityCode(a.code || "");
};

const handleSelectLabor = (l: Labor) => {
  setEditingLaborId(l.id);
  setNewLaborActivityId(String(l.activity_id));
  setNewLaborName(l.name || "");
  setNewLaborCode(l.code || "");
  setNewLaborEffortFactor(l.effort_factor != null ? String(l.effort_factor) : "");
  setNewLaborTargetSpeed(l.target_speed_kmh != null ? String(l.target_speed_kmh) : "");
};

  // filtros en panel de labores
  const [filterLaborsActivityId, setFilterLaborsActivityId] = useState<string>("");

  // ---------- loaders ----------
  const loadMachines = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBaseUrl}/machines`);
      if (!res.ok) throw new Error(`Error ${res.status}: ${await res.text()}`);
      setMachines(await res.json());
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "No se pudieron cargar las máquinas.");
    } finally {
      setLoading(false);
    }
  };

  const loadCostCenters = async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/cost_centers`);
      if (res.ok) setCostCenters(await res.json());
    } catch (e) {
      console.error("Error cargando centros de costo", e);
    }
  };

  const loadActivities = async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/activities`);
      if (!res.ok) throw new Error(`Error ${res.status}: ${await res.text()}`);
      setActivities(await res.json());
    } catch (e) {
      console.error("Error cargando actividades", e);
    }
  };

  const loadLabors = async (activityId?: number) => {
    try {
      const url = activityId
        ? `${apiBaseUrl}/labors?activity_id=${activityId}`
        : `${apiBaseUrl}/labors`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Error ${res.status}: ${await res.text()}`);
      const data: Labor[] = await res.json();
      if (activityId) {
        setLaborsByActivity(data);
      } else {
        setLabors(data);
      }
    } catch (e) {
      console.error("Error cargando labores", e);
    }
  };

  const refreshLabors = async () => {
  // mantén “labors” (todas) actualizado para getLaborName()
  await loadLabors();
  if (filterLaborsActivityId) {
    await loadLabors(Number(filterLaborsActivityId)); // laborsByActivity
  }
};


  useEffect(() => {
    void loadMachines();
    void loadCostCenters();
    void loadActivities();
    void loadLabors(); // todas (para panel de maestros)
  }, []);

  // cuando cambia la actividad por defecto del formulario de máquina,
  // cargamos labores dependientes para ese select
  useEffect(() => {
    if (!defaultActivityId) {
      setLaborsByActivity([]);
      setDefaultLaborId("");
      return;
    }
    void loadLabors(Number(defaultActivityId));
    setDefaultLaborId("");
  }, [defaultActivityId]);

  // filtro del panel de labores
  useEffect(() => {
    if (!filterLaborsActivityId) {
      // mostrar todas
      void loadLabors();
    } else {
      void loadLabors(Number(filterLaborsActivityId));
    }
  }, [filterLaborsActivityId]);

  // ---------- helpers ----------
  const resetForm = () => {
    setName("");
    setPlate("");
    setDescription("");
    setCostCenterId("");
    setTankCapacity("");
    setFuelPerHour("");
    setFuelPerKm("");
    setDefaultActivityId("");
    setDefaultLaborId("");
    setEditingMachineId(null);
    setSaveError(null);
    setSaveSuccess(null);
  };

  const parseNumberOrNull = (value: string): number | null => {
    if (!value.trim()) return null;
    const parsed = parseFloat(value.replace(",", "."));
    if (Number.isNaN(parsed)) return null;
    return parsed;
  };

  const getCostCenterName = (id?: number | null) => {
    if (!id) return "—";
    const cc = costCenters.find((c) => c.id === id);
    return cc ? cc.name : `ID ${id}`;
  };

  const getActivityName = (id?: number | null) => {
    if (!id) return "—";
    const a = activities.find((x) => x.id === id);
    return a ? a.name : `ID ${id}`;
  };

  const getLaborName = (id?: number | null) => {
    if (!id) return "—";
    const l = labors.find((x) => x.id === id);
    return l ? l.name : `ID ${id}`;
  };

  const formatNumber = (n?: number | null, decs = 2) => {
    if (n == null) return "—";
    return n.toFixed(decs).replace(".", ",");
  };

  // ---------- submit máquina ----------
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      setSaveError("El nombre de la máquina es obligatorio.");
      setSaveSuccess(null);
      return;
    }

    try {
      setSaving(true);
      setSaveError(null);
      setSaveSuccess(null);

      const body: any = {
        name: name.trim(),
        plate: plate.trim() || null,
        description: description.trim() || null,
        cost_center_id: costCenterId ? Number(costCenterId) : null,
        tank_capacity_liters: parseNumberOrNull(tankCapacity),
        fuel_consumption_lph: parseNumberOrNull(fuelPerHour),
        fuel_consumption_lpkm: parseNumberOrNull(fuelPerKm),
        default_activity_id: defaultActivityId ? Number(defaultActivityId) : null,
        default_labor_id: defaultLaborId ? Number(defaultLaborId) : null,
      };

      let url = `${apiBaseUrl}/machines`;
      let method: "POST" | "PUT" = "POST";
      if (isEditing && editingMachineId !== null) {
        url = `${apiBaseUrl}/machines/${editingMachineId}`;
        method = "PUT";
      }

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Error ${res.status}: ${await res.text()}`);

      setSaveSuccess(isEditing ? "Máquina actualizada correctamente." : "Máquina creada correctamente.");
      await loadMachines();
      resetForm();
    } catch (e: any) {
      console.error(e);
      setSaveError(e?.message || "No se pudo guardar la máquina.");
      setSaveSuccess(null);
    } finally {
      setSaving(false);
    }
  };

  const handleEditClick = (m: Machine) => {
    setEditingMachineId(m.id);
    setName(m.name || "");
    setPlate(m.plate || "");
    setDescription(m.description || "");
    setCostCenterId(m.cost_center_id ? String(m.cost_center_id) : "");
    setTankCapacity(m.tank_capacity_liters != null ? String(m.tank_capacity_liters) : "");
    setFuelPerHour(m.fuel_consumption_lph != null ? String(m.fuel_consumption_lph) : "");
    setFuelPerKm(m.fuel_consumption_lpkm != null ? String(m.fuel_consumption_lpkm) : "");
    setDefaultActivityId(m.default_activity_id ? String(m.default_activity_id) : "");
    setDefaultLaborId(m.default_labor_id ? String(m.default_labor_id) : "");
    setSaveError(null);
    setSaveSuccess(null);

    // cargar labores dependientes si había actividad por defecto
    if (m.default_activity_id) void loadLabors(Number(m.default_activity_id));
  };

  // ---------- crear actividad ----------
const handleUpsertActivity = async (e: React.FormEvent) => {
  e.preventDefault();
  if (!newActivityName.trim()) return;

  const body = {
    name: newActivityName.trim(),
    code: newActivityCode.trim() || null,
  };

  const url = isEditingActivity
    ? `${apiBaseUrl}/activities/${editingActivityId}`
    : `${apiBaseUrl}/activities`;

  const method: "POST" | "PUT" = isEditingActivity ? "PUT" : "POST";

  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    alert(`Error guardando actividad: ${await res.text()}`);
    return;
  }

  await loadActivities();
  resetActivityForm();
};

  // ---------- crear labor ----------
const handleUpsertLabor = async (e: React.FormEvent) => {
  e.preventDefault();
  if (!newLaborName.trim() || !newLaborActivityId) return;

  const body = {
    activity_id: Number(newLaborActivityId),
    name: newLaborName.trim(),
    code: newLaborCode.trim() || null,
    effort_factor: parseNumberOrNull(newLaborEffortFactor),
    target_speed_kmh: parseNumberOrNull(newLaborTargetSpeed),
  };

  const url = isEditingLabor
    ? `${apiBaseUrl}/labors/${editingLaborId}`
    : `${apiBaseUrl}/labors`;

  const method: "POST" | "PUT" = isEditingLabor ? "PUT" : "POST";

  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    alert(`Error guardando labor: ${await res.text()}`);
    return;
  }

  await refreshLabors();
  resetLaborForm();
};


  return (
    <section className="card entity-page">
      {/* ============ FORM MÁQUINA ============ */}
      <div>
        <div className="card-header">
          <div>
            <div className="card-title">
              Máquinas {isEditing && <span>(editando #{editingMachineId})</span>}
            </div>
            <div className="card-subtitle">
              Registro de tractores/equipos. Define capacidad de estanque, consumos y
              actividad/labor por defecto para prellenar el inicio de recorridos.
            </div>
          </div>
        </div>

        <form className="form-grid" onSubmit={handleSubmit}>
          <div className="form-field">
            <label className="form-label">Nombre máquina *</label>
            <input className="form-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej: Tractor New Holland #1" />
          </div>

          <div className="form-field">
            <label className="form-label">Patente / Código interno</label>
            <input className="form-input" value={plate} onChange={(e) => setPlate(e.target.value)} placeholder="Ej: XX-1234 o MCH-001" />
          </div>

          <div className="form-field">
            <label className="form-label">Centro de costo asociado</label>
            <select className="form-select" value={costCenterId} onChange={(e) => setCostCenterId(e.target.value)}>
              <option value="">Sin centro de costo</option>
              {costCenters.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          {/* Capacidad / consumos */}
          <div className="form-field">
            <label className="form-label">Capacidad estanque (L)</label>
            <input className="form-input" type="number" min={0} step="0.1" value={tankCapacity} onChange={(e) => setTankCapacity(e.target.value)} placeholder="Ej: 120" />
          </div>

          <div className="form-field">
            <label className="form-label">Consumo promedio (L/h)</label>
            <input className="form-input" type="number" min={0} step="0.1" value={fuelPerHour} onChange={(e) => setFuelPerHour(e.target.value)} placeholder="Ej: 9.5" />
          </div>

          <div className="form-field">
            <label className="form-label">Consumo promedio (L/km)</label>
            <input className="form-input" type="number" min={0} step="0.01" value={fuelPerKm} onChange={(e) => setFuelPerKm(e.target.value)} placeholder="Ej: 0.40" />
          </div>

          {/* Actividad/Labor por defecto */}
          <div className="form-field">
            <label className="form-label">Actividad por defecto</label>
            <select className="form-select" value={defaultActivityId} onChange={(e) => setDefaultActivityId(e.target.value)}>
              <option value="">—</option>
              {activities.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>

          <div className="form-field">
            <label className="form-label">Labor por defecto</label>
            <select className="form-select" value={defaultLaborId} onChange={(e) => setDefaultLaborId(e.target.value)} disabled={!defaultActivityId}>
              <option value="">{defaultActivityId ? "Selecciona…" : "—"}</option>
              {laborsByActivity.map((l) => (
                <option key={l.id} value={l.id}>{l.name}</option>
              ))}
            </select>
          </div>

          <div className="form-field">
            <label className="form-label">Descripción</label>
            <textarea className="form-input" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Notas (modelo, implementos, etc.)" />
          </div>

          {saveError && <div className="tracker-error">⚠️ {saveError}</div>}
          {saveSuccess && <div className="tracker-success" style={{ marginTop: 4 }}>✅ {saveSuccess}</div>}

          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <button type="submit" className="form-button-primary" disabled={saving}>
              {saving ? "Guardando..." : isEditing ? "Guardar cambios" : "Agregar máquina"}
            </button>
            {isEditing && (
              <button type="button" className="form-button-ghost" onClick={resetForm} disabled={saving}>
                Cancelar edición
              </button>
            )}
          </div>
        </form>
      </div>

      {/* ============ TABLA MÁQUINAS ============ */}
      <div>
        {error && <div className="tracker-error">⚠️ {error}</div>}
        <div className="entity-table-wrapper">
          {loading ? (
            <div className="sessions-loading">Cargando máquinas…</div>
          ) : machines.length === 0 ? (
            <div className="sessions-empty">No hay máquinas registradas.</div>
          ) : (
            <table className="entity-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Nombre</th>
                  <th>Patente / Código</th>
                  <th>Centro de costo</th>
                  <th>Estanque (L)</th>
                  <th>Consumo (L/h)</th>
                  <th>Consumo (L/km)</th>
                  <th>Actividad def.</th>
                  <th>Labor def.</th>

                  <th style={{ width: 1 }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {machines.map((m) => (
                  <tr key={m.id}>
                    <td>{m.id}</td>
                    <td>{m.name}</td>
                    <td>{m.plate || "—"}</td>
                    <td>{getCostCenterName(m.cost_center_id)}</td>
                    <td>{formatNumber(m.tank_capacity_liters)}</td>
                    <td>{formatNumber(m.fuel_consumption_lph)}</td>
                    <td>{formatNumber(m.fuel_consumption_lpkm, 3)}</td>
                    <td>{getActivityName(m.default_activity_id)}</td>

                    <td>{getLaborName(m.default_labor_id)}</td>
                    <td>
                      <button
                        type="button"
                        className="form-button-secondary"
                        style={{ padding: "4px 10px", fontSize: "0.78rem" }}
                        onClick={() => handleEditClick(m)}
                      >
                        Editar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* ============ MAESTRO: ACTIVIDADES ============ */}
      <section className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <div>
            <div className="card-title">Actividades</div>
            <div className="card-subtitle">Catálogo de actividades (padre de las labores).</div>
          </div>
        </div>

        <form className="form-grid" onSubmit={handleUpsertActivity}>
          <div className="form-field">
            <label className="form-label">Nombre *</label>
            <input className="form-input" value={newActivityName} onChange={(e) => setNewActivityName(e.target.value)} placeholder="Ej: Cosecha" />
          </div>
          <div className="form-field">
            <label className="form-label">Código</label>
            <input className="form-input" value={newActivityCode} onChange={(e) => setNewActivityCode(e.target.value)} placeholder="Opcional" />
          </div>
          <div>
            <button type="submit" className="form-button-primary">
  {isEditingActivity ? "Guardar cambios" : "Agregar actividad"}
</button>

{isEditingActivity && (
  <button type="button" className="form-button-ghost" onClick={resetActivityForm}>
    Cancelar edición
  </button>
)}

          </div>
        </form>

        <div className="entity-table-wrapper">
          {activities.length === 0 ? (
            <div className="sessions-empty">Sin actividades.</div>
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
  {activities.map((a) => (
    <tr
      key={a.id}
      onClick={() => handleSelectActivity(a)}
      style={{ cursor: "pointer" }}
      className={editingActivityId === a.id ? "is-selected" : ""}
      title="Click para editar"
    >
      <td>{a.id}</td>
      <td>{a.name}</td>
      <td>{a.code || "—"}</td>
    </tr>
  ))}
</tbody>

            </table>
          )}
        </div>
      </section>

      {/* ============ MAESTRO: LABORES ============ */}
      <section className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <div>
            <div className="card-title">Labores</div>
            <div className="card-subtitle">
              Catálogo de labores (hijas de una actividad). Usa el filtro por actividad para listar.
            </div>
          </div>
        </div>

        {/* crear labor */}
        <form className="form-grid" onSubmit={handleUpsertLabor}>
          <div className="form-field">
            <label className="form-label">Actividad *</label>
            <select className="form-select" value={newLaborActivityId} onChange={(e) => setNewLaborActivityId(e.target.value)}>
              <option value="">Selecciona…</option>
              {activities.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label className="form-label">Nombre labor *</label>
            <input className="form-input" value={newLaborName} onChange={(e) => setNewLaborName(e.target.value)} placeholder="Ej: Cosecha Manzana Fuji" />
          </div>
          <div className="form-field">
            <label className="form-label">Código</label>
            <input className="form-input" value={newLaborCode} onChange={(e) => setNewLaborCode(e.target.value)} placeholder="Opcional" />
          </div>
          <div className="form-field">
  <label className="form-label">Factor de esfuerzo</label>
  <input
    className="form-input"
    type="number"
    min={0}
    step="0.01"
    value={newLaborEffortFactor}
    onChange={(e) => setNewLaborEffortFactor(e.target.value)}
    placeholder="Ej: 1.30"
  />
</div>

<div className="form-field">
  <label className="form-label">Velocidad objetivo (km/h)</label>
  <input
    className="form-input"
    type="number"
    min={0}
    step="0.1"
    value={newLaborTargetSpeed}
    onChange={(e) => setNewLaborTargetSpeed(e.target.value)}
    placeholder="Ej: 6.0"
  />
</div>

          <div>
           <button type="submit" className="form-button-primary">
  {isEditingLabor ? "Guardar cambios" : "Agregar labor"}
</button>

{isEditingLabor && (
  <button type="button" className="form-button-ghost" onClick={resetLaborForm}>
    Cancelar edición
  </button>
)}

          </div>
        </form>

        {/* filtro y tabla */}
        <div className="form-grid" style={{ marginTop: 8 }}>
          <div className="form-field">
            <label className="form-label">Filtrar por actividad</label>
            <select className="form-select" value={filterLaborsActivityId} onChange={(e) => setFilterLaborsActivityId(e.target.value)}>
              <option value="">Todas</option>
              {activities.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="entity-table-wrapper">
          {(filterLaborsActivityId ? laborsByActivity : labors).length === 0 ? (
            <div className="sessions-empty">Sin labores para el criterio.</div>
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
  {(filterLaborsActivityId ? laborsByActivity : labors).map((l) => (
    <tr
      key={l.id}
      onClick={() => handleSelectLabor(l)}
      style={{ cursor: "pointer" }}
      className={editingLaborId === l.id ? "is-selected" : ""}
      title="Click para editar"
    >
      <td>{l.id}</td>
      <td>{getActivityName(l.activity_id)}</td>
      <td>{l.name}</td>
      <td>{l.code || "—"}</td>
      <td>{l.effort_factor != null ? String(l.effort_factor).replace(".", ",") : "—"}</td>
      <td>{l.target_speed_kmh != null ? String(l.target_speed_kmh).replace(".", ",") : "—"}</td>
    </tr>
  ))}
</tbody>

            </table>
          )}
        </div>
      </section>
    </section>
  );
};

export default MachinesPage;
