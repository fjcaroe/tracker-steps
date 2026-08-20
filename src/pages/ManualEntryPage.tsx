import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { apiFetch, apiJson } from "../services/http";
import "./ManualEntryPage.css";

type CatalogItem = { id: number; name: string };
type Labor = CatalogItem & { activity_id: number };
type WorkOrder = {
  id: number;
  code: string;
  work_date: string;
  season: string;
  machine_id?: number | null;
  activity_id: number;
  labor_id: number;
  cost_center_id?: number | null;
  field_id?: number | null;
  implement_id?: number | null;
  hourmeter_initial?: number | null;
  hourmeter_final?: number | null;
  fuel_tank_start_liters?: number | null;
  fuel_refill_liters?: number | null;
  fuel_tank_end_liters?: number | null;
  notes?: string | null;
};

type Draft = {
  workDate: string;
  season: string;
  machineId: string;
  activityId: string;
  laborId: string;
  costCenterId: string;
  fieldId: string;
  implementId: string;
  hourmeterInitial: string;
  hourmeterFinal: string;
  fuelTankStart: string;
  fuelRefill: string;
  fuelTankEnd: string;
  notes: string;
};

type Catalogs = {
  machines: CatalogItem[];
  activities: CatalogItem[];
  labors: Labor[];
  costCenters: CatalogItem[];
  fields: CatalogItem[];
  implements: CatalogItem[];
};

const emptyCatalogs: Catalogs = { machines: [], activities: [], labors: [], costCenters: [], fields: [], implements: [] };

function localDateValue(date = new Date()) {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

function currentSeason() {
  const now = new Date();
  const first = now.getMonth() >= 6 ? now.getFullYear() : now.getFullYear() - 1;
  return `${first}-${first + 1}`;
}

function blankDraft(): Draft {
  return {
    workDate: localDateValue(), season: currentSeason(), machineId: "", activityId: "", laborId: "",
    costCenterId: "", fieldId: "", implementId: "", hourmeterInitial: "", hourmeterFinal: "",
    fuelTankStart: "", fuelRefill: "", fuelTankEnd: "", notes: "",
  };
}

function optionalNumber(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

function idOrNull(value: string): number | null {
  return value ? Number(value) : null;
}

function nameFor(items: CatalogItem[], id?: number | null) {
  if (id == null) return "—";
  return items.find((item) => item.id === id)?.name ?? `N.º ${id}`;
}

function displayDate(value: string) {
  const date = new Date(`${value.slice(0, 10)}T12:00`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("es-CL");
}

function generatedCode(date: string) {
  const now = new Date();
  const clock = now.toTimeString().slice(0, 8).replaceAll(":", "");
  return `MAN-${date.replaceAll("-", "")}-${clock}${String(now.getMilliseconds()).padStart(3, "0")}`;
}

export default function ManualEntryPage() {
  const [catalogs, setCatalogs] = useState<Catalogs>(emptyCatalogs);
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [draft, setDraft] = useState<Draft>(blankDraft);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [machines, activities, labors, costCenters, fields, implementsList, workOrders] = await Promise.all([
        apiJson<CatalogItem[]>("/machines"), apiJson<CatalogItem[]>("/activities"), apiJson<Labor[]>("/labors"),
        apiJson<CatalogItem[]>("/cost_centers"), apiJson<CatalogItem[]>("/fields"), apiJson<CatalogItem[]>("/implements"),
        apiJson<WorkOrder[]>("/work_orders"),
      ]);
      setCatalogs({ machines, activities, labors, costCenters, fields, implements: implementsList });
      setOrders(Array.isArray(workOrders) ? workOrders : []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudieron cargar los registros manuales.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadData(); }, [loadData]);

  const availableLabors = useMemo(() => {
    if (!draft.activityId) return catalogs.labors;
    return catalogs.labors.filter((labor) => labor.activity_id === Number(draft.activityId));
  }, [catalogs.labors, draft.activityId]);

  const validationError = useMemo(() => {
    if (editingId == null) {
      if (!draft.workDate) return "Indique la fecha del trabajo.";
      if (!draft.season.trim()) return "Indique la temporada.";
      if (!draft.machineId) return "Seleccione la máquina.";
      if (!draft.activityId) return "Seleccione la actividad.";
      if (!draft.laborId) return "Seleccione la labor.";
    }
    const numericFields = [draft.hourmeterInitial, draft.hourmeterFinal, draft.fuelTankStart, draft.fuelRefill, draft.fuelTankEnd];
    if (numericFields.some((value) => value && (optionalNumber(value) == null || Number(value.replace(",", ".")) < 0))) return "Revise los valores de horómetro y combustible. Solo se aceptan números positivos.";
    const initial = optionalNumber(draft.hourmeterInitial);
    const final = optionalNumber(draft.hourmeterFinal);
    if (initial != null && final != null && final < initial) return "El horómetro final no puede ser menor que el inicial.";
    return null;
  }, [draft, editingId]);

  const update = (field: keyof Draft, value: string) => {
    setDraft((current) => {
      if (field === "activityId" && current.activityId !== value) return { ...current, activityId: value, laborId: "" };
      return { ...current, [field]: value };
    });
    setError(null);
    setMessage(null);
  };

  const requestReview = (event: FormEvent) => {
    event.preventDefault();
    if (validationError) { setError(validationError); return; }
    setReviewing(true);
  };

  const resetForm = () => {
    setDraft(blankDraft());
    setEditingId(null);
    setReviewing(false);
  };

  const save = async () => {
    if (validationError) { setError(validationError); return; }
    setSaving(true);
    setError(null);
    try {
      const common = {
        implement_id: idOrNull(draft.implementId),
        hourmeter_initial: optionalNumber(draft.hourmeterInitial), hourmeter_final: optionalNumber(draft.hourmeterFinal),
        fuel_tank_start_liters: optionalNumber(draft.fuelTankStart), fuel_refill_liters: optionalNumber(draft.fuelRefill),
        fuel_tank_end_liters: optionalNumber(draft.fuelTankEnd), notes: draft.notes.trim() || null,
      };
      if (editingId != null) {
        await apiFetch(`/work_orders/${editingId}`, { method: "PUT", body: JSON.stringify(common) });
        setMessage("El parte de trabajo fue actualizado correctamente.");
      } else {
        await apiFetch("/work_orders", { method: "POST", body: JSON.stringify({
          code: generatedCode(draft.workDate), work_date: draft.workDate, season: draft.season.trim(),
          machine_id: Number(draft.machineId), activity_id: Number(draft.activityId), labor_id: Number(draft.laborId),
          cost_center_id: idOrNull(draft.costCenterId), field_id: idOrNull(draft.fieldId), ...common,
        }) });
        setMessage("El parte de trabajo fue guardado en Tracker y ya está disponible para los demás usuarios.");
      }
      resetForm();
      await loadData();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo guardar. Revise los datos e intente nuevamente.");
    } finally {
      setSaving(false);
      setReviewing(false);
    }
  };

  const edit = (order: WorkOrder) => {
    setDraft({
      workDate: order.work_date.slice(0, 10), season: order.season, machineId: order.machine_id?.toString() ?? "",
      activityId: order.activity_id.toString(), laborId: order.labor_id.toString(), costCenterId: order.cost_center_id?.toString() ?? "",
      fieldId: order.field_id?.toString() ?? "", implementId: order.implement_id?.toString() ?? "",
      hourmeterInitial: order.hourmeter_initial?.toString() ?? "", hourmeterFinal: order.hourmeter_final?.toString() ?? "",
      fuelTankStart: order.fuel_tank_start_liters?.toString() ?? "", fuelRefill: order.fuel_refill_liters?.toString() ?? "",
      fuelTankEnd: order.fuel_tank_end_liters?.toString() ?? "", notes: order.notes ?? "",
    });
    setEditingId(order.id);
    setReviewing(false);
    setError(null);
    setMessage("Está editando las lecturas y observaciones de un parte existente.");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const rows = useMemo(() => {
    const term = query.trim().toLocaleLowerCase("es");
    return [...orders].sort((a, b) => b.work_date.localeCompare(a.work_date)).filter((order) => {
      const values = [order.code, order.season, nameFor(catalogs.machines, order.machine_id), nameFor(catalogs.activities, order.activity_id), nameFor(catalogs.labors, order.labor_id), order.notes ?? ""];
      return !term || values.some((value) => value.toLocaleLowerCase("es").includes(term));
    });
  }, [catalogs, orders, query]);

  const locked = editingId != null;
  return <main className="manual-page">
    <section className="manual-intro"><span className="manual-intro__number">1</span><div><h2>Complete los datos con calma</h2><p>Los campos obligatorios están marcados. Antes de guardar verá un resumen completo para revisar.</p></div><div className="manual-intro__status"><b>{orders.length}</b><span>partes disponibles</span></div></section>
    <div className="manual-layout">
      <form className="manual-card manual-form" onSubmit={requestReview} noValidate>
        <header><div><span>Paso 1 de 2</span><h2>{locked ? `Editar parte ${editingId}` : "Nuevo ingreso manual"}</h2><p>{locked ? "Por seguridad, al editar solo se cambian lecturas, implemento y observaciones." : "Este registro quedará guardado centralmente como parte de trabajo."}</p></div></header>
        {message && <div className="manual-alert is-success" role="status">✓ {message}</div>}{error && <div className="manual-alert is-error" role="alert">{error}</div>}
        {!locked ? <fieldset><legend>Identificación del trabajo</legend><div className="manual-fields is-three">
          <Field label="Fecha" required><input type="date" value={draft.workDate} onChange={(e) => update("workDate", e.target.value)} /></Field>
          <Field label="Temporada" required><input value={draft.season} placeholder="Ejemplo: 2026-2027" onChange={(e) => update("season", e.target.value)} /></Field>
          <SelectField label="Máquina" required value={draft.machineId} items={catalogs.machines} onChange={(value) => update("machineId", value)} />
          <SelectField label="Actividad" required value={draft.activityId} items={catalogs.activities} onChange={(value) => update("activityId", value)} />
          <SelectField label="Labor" required value={draft.laborId} items={availableLabors} onChange={(value) => update("laborId", value)} />
          <SelectField label="Predio o lote" value={draft.fieldId} items={catalogs.fields} onChange={(value) => update("fieldId", value)} />
          <SelectField label="Centro de costo" value={draft.costCenterId} items={catalogs.costCenters} onChange={(value) => update("costCenterId", value)} />
        </div></fieldset> : <section className="manual-locked-summary"><b>Identificación original protegida</b><p>{displayDate(draft.workDate)} · {draft.season} · {nameFor(catalogs.activities, idOrNull(draft.activityId))} · {nameFor(catalogs.labors, idOrNull(draft.laborId))}</p><small>La API conserva estos datos, pero al editar solo permite cambiar lecturas, implemento y observaciones.</small></section>}
        <fieldset><legend>Lecturas y detalles</legend><div className="manual-fields is-three">
          <SelectField label="Implemento" value={draft.implementId} items={catalogs.implements} onChange={(value) => update("implementId", value)} />
          <NumberField label="Horómetro inicial" unit="h" value={draft.hourmeterInitial} onChange={(value) => update("hourmeterInitial", value)} />
          <NumberField label="Horómetro final" unit="h" value={draft.hourmeterFinal} onChange={(value) => update("hourmeterFinal", value)} />
          <NumberField label="Combustible inicial" unit="L" value={draft.fuelTankStart} onChange={(value) => update("fuelTankStart", value)} />
          <NumberField label="Carga de combustible" unit="L" value={draft.fuelRefill} onChange={(value) => update("fuelRefill", value)} />
          <NumberField label="Combustible final" unit="L" value={draft.fuelTankEnd} onChange={(value) => update("fuelTankEnd", value)} />
          <Field label="Observaciones" wide><textarea rows={4} placeholder="Ejemplo: información transcrita desde la libreta del operador" value={draft.notes} onChange={(e) => update("notes", e.target.value)} /></Field>
        </div></fieldset>
        <div className="manual-actions"><button type="submit" className="manual-button is-primary" disabled={saving}>{saving ? "Guardando…" : "Revisar antes de guardar →"}</button>{locked && <button type="button" className="manual-button" onClick={resetForm}>Cancelar edición</button>}</div>
      </form>
      <aside className="manual-card manual-guide"><span className="manual-intro__number">2</span><h2>Luego revise y confirme</h2><p>Nada se guarda al presionar “Revisar”. Podrá volver y corregir cualquier dato.</p><ul><li>Use la fecha del documento original.</li><li>Deje vacío cualquier valor que desconozca.</li><li>Revise especialmente máquina, actividad y labor.</li></ul><div className="manual-storage-note"><b>Registro centralizado</b><p>Al confirmar, el parte se guarda en Tracker y queda disponible para los demás usuarios autorizados. No se mezcla con las sesiones GPS.</p></div></aside>
    </div>

    {reviewing && <div className="manual-review-backdrop" role="dialog" aria-modal="true" aria-labelledby="manual-review-title"><section className="manual-review"><header><span>Último paso</span><h2 id="manual-review-title">Revise el parte de trabajo</h2><p>Confirme que la información coincida con el documento original.</p></header><dl>
      <Review label="Fecha" value={displayDate(draft.workDate)} /><Review label="Temporada" value={draft.season} /><Review label="Máquina" value={locked ? "Se conserva sin cambios" : nameFor(catalogs.machines, idOrNull(draft.machineId))} /><Review label="Actividad" value={nameFor(catalogs.activities, idOrNull(draft.activityId))} /><Review label="Labor" value={nameFor(catalogs.labors, idOrNull(draft.laborId))} /><Review label="Predio o lote" value={nameFor(catalogs.fields, idOrNull(draft.fieldId))} /><Review label="Centro de costo" value={nameFor(catalogs.costCenters, idOrNull(draft.costCenterId))} /><Review label="Implemento" value={nameFor(catalogs.implements, idOrNull(draft.implementId))} /><Review label="Horómetro" value={`${draft.hourmeterInitial || "—"} → ${draft.hourmeterFinal || "—"} h`} /><Review label="Combustible" value={`${draft.fuelTankStart || "—"} + ${draft.fuelRefill || "0"} → ${draft.fuelTankEnd || "—"} L`} /><Review label="Observaciones" value={draft.notes} />
    </dl><div className="manual-actions"><button type="button" className="manual-button" onClick={() => setReviewing(false)}>← Volver y corregir</button><button type="button" className="manual-button is-primary" onClick={() => void save()} disabled={saving}>{saving ? "Guardando…" : "✓ Confirmar y guardar"}</button></div></section></div>}

    <section className="manual-card manual-records"><header><div><span>Revisión administrativa</span><h2>Partes de trabajo registrados</h2><p>Consulte o corrija lecturas y observaciones sin entrar al historial GPS.</p></div><button type="button" className="manual-button" onClick={() => void loadData()} disabled={loading}>{loading ? "Actualizando…" : "Actualizar lista"}</button></header><div className="manual-records__toolbar"><label><span>Buscar partes</span><input type="search" placeholder="Código, máquina, actividad o labor…" value={query} onChange={(e) => setQuery(e.target.value)} /></label><p>{rows.length} resultado{rows.length === 1 ? "" : "s"}</p></div>
      {loading ? <div className="manual-empty">Cargando partes de trabajo…</div> : rows.length ? <div className="manual-table-wrap"><table><thead><tr><th>Fecha / código</th><th>Predio / centro</th><th>Actividad / labor</th><th>Temporada</th><th>Horómetro</th><th>Acción</th></tr></thead><tbody>{rows.map((order) => <tr key={order.id}><td><b>{displayDate(order.work_date)}</b><small>{order.code}</small></td><td><b>{nameFor(catalogs.fields, order.field_id)}</b><small>{nameFor(catalogs.costCenters, order.cost_center_id)}</small></td><td><b>{nameFor(catalogs.activities, order.activity_id)}</b><small>{nameFor(catalogs.labors, order.labor_id)}</small></td><td>{order.season}</td><td>{order.hourmeter_initial ?? "—"} → {order.hourmeter_final ?? "—"}</td><td><button type="button" onClick={() => edit(order)}>Revisar / editar</button></td></tr>)}</tbody></table></div> : <div className="manual-empty">No hay partes que coincidan con la búsqueda.</div>}
    </section>
  </main>;
}

function Field({ label, required, wide, children }: { label: string; required?: boolean; wide?: boolean; children: ReactNode }) {
  return <label className={wide ? "manual-field--wide" : undefined}><span>{label} {required && <b>*</b>}</span>{children}</label>;
}

function SelectField({ label, value, items, required, onChange }: { label: string; value: string; items: CatalogItem[]; required?: boolean; onChange: (value: string) => void }) {
  return <Field label={label} required={required}><select value={value} onChange={(event) => onChange(event.target.value)}><option value="">{required ? "Seleccione una opción" : "Sin informar"}</option>{items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>;
}

function NumberField({ label, unit, value, onChange }: { label: string; unit: string; value: string; onChange: (value: string) => void }) {
  return <Field label={label}><span className="manual-input-unit"><input inputMode="decimal" placeholder="0,0" value={value} onChange={(event) => onChange(event.target.value)} /><em>{unit}</em></span></Field>;
}

function Review({ label, value }: { label: string; value: string }) {
  return <div><dt>{label}</dt><dd>{value || "Sin informar"}</dd></div>;
}
