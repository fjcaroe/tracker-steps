import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, apiFetch, apiJson } from "../services/http";
import FieldPolygonEditor, { type PolygonPoint } from "./FieldPolygonEditor";
import "./MastersAdminModal.css";

export type MasterKind = "machines" | "drivers" | "activities" | "labors" | "implements" | "costCenters" | "species" | "varieties" | "regions" | "communes" | "fundos" | "sectors" | "fields";
type Entity = { id: number; name: string; [key: string]: unknown };
type Catalogs = { costCenters: Entity[]; activities: Entity[]; labors: Entity[]; regions: Entity[]; communes: Entity[]; fundos: Entity[]; species: Entity[] };
type Draft = Record<string, string>;

const meta: Record<MasterKind, { title: string; singular: string; endpoint: string; update?: "PUT" | "PATCH"; canDelete?: boolean }> = {
  machines: { title: "Máquinas", singular: "máquina", endpoint: "/machines", update: "PUT", canDelete: true },
  drivers: { title: "Conductores", singular: "conductor", endpoint: "/drivers", update: "PATCH", canDelete: true },
  activities: { title: "Actividades", singular: "actividad", endpoint: "/activities", update: "PUT", canDelete: true },
  labors: { title: "Labores", singular: "labor", endpoint: "/labors", update: "PUT", canDelete: true },
  implements: { title: "Implementos", singular: "implemento", endpoint: "/implements", update: "PATCH", canDelete: true },
  costCenters: { title: "Centros de costo", singular: "centro de costo", endpoint: "/cost_centers", update: "PATCH", canDelete: true },
  species: { title: "Especies", singular: "especie", endpoint: "/species", update: "PATCH", canDelete: true },
  varieties: { title: "Variedades", singular: "variedad", endpoint: "/varieties", update: "PATCH", canDelete: true },
  regions: { title: "Regiones", singular: "región", endpoint: "/regions", update: "PATCH", canDelete: true },
  communes: { title: "Comunas", singular: "comuna", endpoint: "/communes", update: "PATCH", canDelete: true },
  fundos: { title: "Fundos", singular: "fundo", endpoint: "/fundos", update: "PATCH", canDelete: true },
  sectors: { title: "Sectores", singular: "sector", endpoint: "/sectors", update: "PATCH", canDelete: true },
  fields: { title: "Predios y polígonos", singular: "predio", endpoint: "/fields", update: "PUT", canDelete: true },
};

function blankDraft(kind: MasterKind): Draft {
  if (kind === "machines") return { name: "", external_id: "", plate: "", description: "", cost_center_id: "", tank_capacity_liters: "", fuel_consumption_unit: "lph", fuel_consumption_lph: "", fuel_efficiency_kmpl: "", default_activity_id: "", default_labor_id: "" };
  if (kind === "drivers") return { name: "", rut: "", is_active: "true" };
  if (kind === "activities") return { name: "", code: "", is_active: "true" };
  if (kind === "labors") return { name: "", activity_id: "", code: "", effort_factor: "", target_speed_kmh: "", is_active: "true" };
  if (kind === "implements") return { name: "", is_active: "true" };
  if (kind === "costCenters") return { name: "", external_id: "", hectares: "", row_count: "", plant_count: "" };
  if (kind === "species") return { name: "" };
  if (kind === "varieties") return { name: "", species_id: "" };
  if (kind === "regions") return { name: "", code: "" };
  if (kind === "communes") return { name: "", region_id: "" };
  if (kind === "fundos") return { name: "", external_id: "", commune_id: "", address: "", hectares_total: "" };
  if (kind === "sectors") return { name: "", fundo_id: "", external_id: "", sdp_code: "", hectares_total: "" };
  return { name: "", cost_center_id: "", color: "#2f7d5c" };
}

function asString(value: unknown) { return value == null ? "" : String(value); }
function nullableNumber(value: string) { return value.trim() ? Number(value.replace(",", ".")) : null; }
function nullableId(value: string) { return value ? Number(value) : null; }

function apiMessage(error: unknown) {
  if (error instanceof ApiError && error.bodyText) {
    try {
      const body = JSON.parse(error.bodyText) as { detail?: string | { msg?: string }[] };
      if (typeof body.detail === "string") return body.detail;
      if (Array.isArray(body.detail)) return body.detail.map((item) => item.msg).filter(Boolean).join(" · ");
    } catch { /* respuesta no JSON */ }
  }
  return error instanceof Error ? error.message : "Ocurrió un error al guardar.";
}

export default function MastersAdminModal({ kind, onClose, onChanged }: { kind: MasterKind; onClose: () => void; onChanged: () => void }) {
  const config = meta[kind];
  const [items, setItems] = useState<Entity[]>([]);
  const [catalogs, setCatalogs] = useState<Catalogs>({ costCenters: [], activities: [], labors: [], regions: [], communes: [], fundos: [], species: [] });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft>(() => blankDraft(kind));
  const [polygon, setPolygon] = useState<PolygonPoint[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [entities, costCenters, activities, labors, regions, communes, fundos, species] = await Promise.all([
        apiJson<Entity[]>(config.endpoint), apiJson<Entity[]>("/cost_centers"), apiJson<Entity[]>("/activities"), apiJson<Entity[]>("/labors"),
        apiJson<Entity[]>("/regions"), apiJson<Entity[]>("/communes"), apiJson<Entity[]>("/fundos"), apiJson<Entity[]>("/species"),
      ]);
      setItems(entities);
      setCatalogs({ costCenters, activities, labors, regions, communes, fundos, species });
    } catch (cause) { setError(apiMessage(cause)); }
    finally { setLoading(false); }
  }, [config.endpoint]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  const filtered = useMemo(() => {
    const term = query.trim().toLocaleLowerCase("es");
    return items.filter((item) => !term || `${item.name} ${asString(item.plate)} ${asString(item.rut)} ${asString(item.external_id)}`.toLocaleLowerCase("es").includes(term));
  }, [items, query]);

  const select = (item: Entity) => {
    setSelectedId(item.id);
    const next = blankDraft(kind);
    Object.keys(next).forEach((key) => { next[key] = asString(item[key]); });
    setDraft(next);
    setPolygon(Array.isArray(item.polygon) ? item.polygon as PolygonPoint[] : []);
    setError(null); setMessage(null);
  };

  const startNew = () => { setSelectedId(null); setDraft(blankDraft(kind)); setPolygon([]); setError(null); setMessage(null); };
  const update = (key: string, value: string) => { setDraft((current) => ({ ...current, [key]: value })); setError(null); setMessage(null); };

  const validate = () => {
    if (!draft.name?.trim()) return "El nombre es obligatorio.";
    if (kind === "fields" && polygon.length < 3) return "El polígono necesita al menos tres puntos.";
    if (kind === "labors" && !draft.activity_id) return "Seleccione la actividad a la que pertenece la labor.";
    if (kind === "varieties" && !draft.species_id) return "Seleccione la especie a la que pertenece la variedad.";
    if (kind === "communes" && !draft.region_id) return "Seleccione la región.";
    if (kind === "sectors" && !draft.fundo_id) return "Seleccione el fundo.";
    const numberKeys = kind === "machines" ? ["tank_capacity_liters", "fuel_consumption_lph", "fuel_efficiency_kmpl"] : kind === "costCenters" ? ["hectares", "row_count", "plant_count"] : kind === "labors" ? ["effort_factor", "target_speed_kmh"] : kind === "fundos" || kind === "sectors" ? ["hectares_total"] : [];
    if (numberKeys.some((key) => draft[key] && (!Number.isFinite(nullableNumber(draft[key])) || Number(nullableNumber(draft[key])) < 0))) return "Revise los campos numéricos.";
    return null;
  };

  const save = async () => {
    const validation = validate();
    if (validation) { setError(validation); return; }
    setSaving(true); setError(null);
    try {
      let payload: Record<string, unknown>;
      if (kind === "machines") payload = { name: draft.name.trim(), external_id: draft.external_id || null, plate: draft.plate || null, description: draft.description || null, cost_center_id: nullableId(draft.cost_center_id), tank_capacity_liters: nullableNumber(draft.tank_capacity_liters), fuel_consumption_unit: draft.fuel_consumption_unit || "lph", fuel_consumption_lph: nullableNumber(draft.fuel_consumption_lph), fuel_efficiency_kmpl: nullableNumber(draft.fuel_efficiency_kmpl), default_activity_id: nullableId(draft.default_activity_id), default_labor_id: nullableId(draft.default_labor_id) };
      else if (kind === "drivers") payload = { name: draft.name.trim(), rut: draft.rut || null, ...(selectedId != null ? { is_active: draft.is_active === "true" } : {}) };
      else if (kind === "activities") payload = { name: draft.name.trim(), code: draft.code || null, ...(selectedId != null ? { is_active: draft.is_active === "true" } : {}) };
      else if (kind === "labors") payload = { name: draft.name.trim(), activity_id: Number(draft.activity_id), code: draft.code || null, effort_factor: nullableNumber(draft.effort_factor), target_speed_kmh: nullableNumber(draft.target_speed_kmh), ...(selectedId != null ? { is_active: draft.is_active === "true" } : {}) };
      else if (kind === "implements") payload = { name: draft.name.trim(), ...(selectedId != null ? { is_active: draft.is_active === "true" } : {}) };
      else if (kind === "costCenters") payload = { name: draft.name.trim(), external_id: draft.external_id || null, hectares: nullableNumber(draft.hectares), row_count: nullableNumber(draft.row_count), plant_count: nullableNumber(draft.plant_count) };
      else if (kind === "species") payload = { name: draft.name.trim() };
      else if (kind === "varieties") payload = { name: draft.name.trim(), species_id: Number(draft.species_id) };
      else if (kind === "regions") payload = { name: draft.name.trim(), code: draft.code || null };
      else if (kind === "communes") payload = { name: draft.name.trim(), region_id: Number(draft.region_id) };
      else if (kind === "fundos") payload = { name: draft.name.trim(), external_id: draft.external_id || null, commune_id: nullableId(draft.commune_id), address: draft.address || null, hectares_total: nullableNumber(draft.hectares_total) };
      else if (kind === "sectors") payload = { name: draft.name.trim(), fundo_id: Number(draft.fundo_id), external_id: draft.external_id || null, sdp_code: draft.sdp_code || null, hectares_total: nullableNumber(draft.hectares_total) };
      else payload = { name: draft.name.trim(), cost_center_id: nullableId(draft.cost_center_id), color: draft.color || null, polygon };

      if (selectedId == null) await apiFetch(config.endpoint, { method: "POST", body: JSON.stringify(payload) });
      else {
        if (!config.update) { setError(`La API actual permite crear ${config.title.toLocaleLowerCase("es")}, pero todavía no ofrece edición ni eliminación.`); setSaving(false); return; }
        await apiFetch(`${config.endpoint}/${selectedId}`, { method: config.update, body: JSON.stringify(payload) });
      }
      const successMessage = `${config.singular[0].toUpperCase()}${config.singular.slice(1)} ${selectedId == null ? "creado" : "actualizado"} correctamente.`;
      startNew();
      await load();
      onChanged();
      setMessage(successMessage);
    } catch (cause) { setError(apiMessage(cause)); }
    finally { setSaving(false); }
  };

  const remove = async () => {
    if (selectedId == null || !config.canDelete) return;
    const item = items.find((candidate) => candidate.id === selectedId);
    if (!window.confirm(`¿Eliminar ${config.singular} “${item?.name ?? selectedId}”? Si el registro tiene información histórica, dejará de estar disponible para nuevas operaciones sin borrar ese historial.`)) return;
    setSaving(true); setError(null);
    try {
      await apiFetch(`${config.endpoint}/${selectedId}`, { method: "DELETE" });
      startNew(); await load(); onChanged();
      setMessage("El registro fue eliminado.");
    } catch (cause) { setError(apiMessage(cause)); }
    finally { setSaving(false); }
  };

  const readOnlySelection = !config.update && selectedId != null;
  return <div className="master-admin-backdrop" role="dialog" aria-modal="true" aria-labelledby="master-admin-title" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className={`master-admin ${kind === "fields" ? "is-map" : ""}`}>
      <header className="master-admin__head"><div><span className="section-kicker">Administración productiva</span><h2 id="master-admin-title">{config.title}</h2><p>Los cambios se guardan directamente en Tracker.</p></div><button type="button" className="master-admin__close" onClick={onClose} aria-label="Cerrar">×</button></header>
      <div className="master-admin__body">
        <aside className="master-admin__list"><button type="button" className="master-admin__new" onClick={startNew}>＋ Nuevo {config.singular}</button><input type="search" aria-label={`Buscar ${config.title}`} placeholder="Buscar…" value={query} onChange={(event) => setQuery(event.target.value)} />
          <div>{loading ? <p className="master-admin__empty">Cargando…</p> : filtered.map((item) => <button type="button" key={item.id} className={selectedId === item.id ? "is-active" : ""} onClick={() => select(item)}><i style={{ background: kind === "fields" ? asString(item.color) || "#2f7d5c" : undefined }}>{kind === "fields" ? "" : item.name.slice(0, 1).toUpperCase()}</i><span><b>{item.name}</b><small>{itemSubtitle(kind, item)}</small></span><em>›</em></button>)}{!loading && !filtered.length && <p className="master-admin__empty">Sin registros.</p>}</div>
        </aside>
        <form className="master-admin__form" onSubmit={(event) => { event.preventDefault(); void save(); }}>
          <header><div><span>{selectedId == null ? "Nuevo registro" : `Registro N.º ${selectedId}`}</span><h3>{selectedId == null ? `Crear ${config.singular}` : draft.name}</h3></div>{selectedId != null && config.canDelete && <button type="button" className="master-admin__delete" onClick={() => void remove()} disabled={saving}>Eliminar</button>}</header>
          {message && <div className="master-admin__alert is-success">✓ {message}</div>}{error && <div className="master-admin__alert is-error" role="alert">{error}</div>}{readOnlySelection && <div className="master-admin__alert is-warning">Este registro se puede consultar, pero la API actual todavía no permite editarlo ni eliminarlo.</div>}
          <fieldset disabled={readOnlySelection || saving}><MasterFields kind={kind} editorKey={selectedId ?? "new"} draft={draft} catalogs={catalogs} update={update} polygon={polygon} setPolygon={setPolygon} /></fieldset>
          <footer><button type="button" onClick={onClose}>Cerrar</button><button type="submit" className="is-primary" disabled={readOnlySelection || saving}>{saving ? "Guardando…" : selectedId == null ? "Crear registro" : "Guardar cambios"}</button></footer>
        </form>
      </div>
    </section>
  </div>;
}

function itemSubtitle(kind: MasterKind, item: Entity) {
  if (kind === "machines") return asString(item.plate) || "Sin patente";
  if (kind === "drivers") return asString(item.rut) || "Sin RUT";
  if (kind === "activities") return asString(item.code) || "Sin código";
  if (kind === "labors") return asString(item.code) || "Sin código";
  if (kind === "implements") return "Implemento operacional";
  if (kind === "costCenters") return item.hectares != null ? `${item.hectares} ha` : asString(item.external_id) || "Sin superficie";
  if (kind === "varieties") return `Especie N.º ${asString(item.species_id)}`;
  if (kind === "regions") return asString(item.code) || "Sin código";
  if (kind === "communes") return `Región N.º ${asString(item.region_id)}`;
  if (kind === "fundos") return item.hectares_total != null ? `${item.hectares_total} ha` : asString(item.address) || "Sin dirección";
  if (kind === "sectors") return item.hectares_total != null ? `${item.hectares_total} ha` : `Fundo N.º ${asString(item.fundo_id)}`;
  if (kind === "species") return "Catálogo agrícola";
  return `${Array.isArray(item.polygon) ? item.polygon.length : 0} vértices`;
}

function FormField({ label, children, wide }: { label: string; children: ReactNode; wide?: boolean }) { return <label className={wide ? "is-wide" : undefined}><span>{label}</span>{children}</label>; }
function Select({ value, items, onChange, empty = "Sin asignar" }: { value: string; items: Entity[]; onChange: (value: string) => void; empty?: string }) { return <select value={value} onChange={(event) => onChange(event.target.value)}><option value="">{empty}</option>{items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>; }
function Input({ value, onChange, ...props }: { value: string; onChange: (value: string) => void; [key: string]: unknown }) { return <input {...props} value={value} onChange={(event) => onChange(event.target.value)} />; }

function MasterFields({ kind, editorKey, draft, catalogs, update, polygon, setPolygon }: { kind: MasterKind; editorKey: number | string; draft: Draft; catalogs: Catalogs; update: (key: string, value: string) => void; polygon: PolygonPoint[]; setPolygon: (points: PolygonPoint[]) => void }) {
  if (kind === "machines") return <MachineFields draft={draft} catalogs={catalogs} update={update} />;
  if (kind === "drivers") return <DriverFields draft={draft} update={update} />;
  if (kind === "activities") return <ActivityFields draft={draft} update={update} />;
  if (kind === "labors") return <LaborFields draft={draft} catalogs={catalogs} update={update} />;
  if (kind === "implements") return <ImplementFields draft={draft} update={update} />;
  if (kind === "species") return <NameOnlyFields draft={draft} update={update} />;
  if (kind === "costCenters") return <CostCenterFields draft={draft} update={update} />;
  if (kind === "varieties") return <VarietyFields draft={draft} catalogs={catalogs} update={update} />;
  if (kind === "regions") return <RegionFields draft={draft} update={update} />;
  if (kind === "communes") return <CommuneFields draft={draft} catalogs={catalogs} update={update} />;
  if (kind === "fundos") return <FundoFields draft={draft} catalogs={catalogs} update={update} />;
  if (kind === "sectors") return <SectorFields draft={draft} catalogs={catalogs} update={update} />;
  return <FieldFields editorKey={editorKey} draft={draft} catalogs={catalogs} update={update} polygon={polygon} setPolygon={setPolygon} />;
}

function MachineFields({ draft, catalogs, update }: { draft: Draft; catalogs: Catalogs; update: (key: string, value: string) => void }) {
  const labors = draft.default_activity_id ? catalogs.labors.filter((labor) => Number(labor.activity_id) === Number(draft.default_activity_id)) : catalogs.labors;
  return <div className="master-form-grid"><FormField label="Nombre *"><Input value={draft.name} onChange={(v) => update("name", v)} /></FormField><FormField label="Patente"><Input value={draft.plate} onChange={(v) => update("plate", v)} /></FormField><FormField label="Identificador externo"><Input value={draft.external_id} onChange={(v) => update("external_id", v)} /></FormField><FormField label="Centro de costo"><Select value={draft.cost_center_id} items={catalogs.costCenters} onChange={(v) => update("cost_center_id", v)} /></FormField><FormField label="Capacidad estanque (L)"><Input inputMode="decimal" value={draft.tank_capacity_liters} onChange={(v) => update("tank_capacity_liters", v)} /></FormField><FormField label="Unidad de consumo"><select value={draft.fuel_consumption_unit} onChange={(e) => update("fuel_consumption_unit", e.target.value)}><option value="lph">Litros por hora</option><option value="kmpl">Kilómetros por litro</option></select></FormField><FormField label="Consumo (L/h)"><Input inputMode="decimal" value={draft.fuel_consumption_lph} onChange={(v) => update("fuel_consumption_lph", v)} /></FormField><FormField label="Rendimiento (km/L)"><Input inputMode="decimal" value={draft.fuel_efficiency_kmpl} onChange={(v) => update("fuel_efficiency_kmpl", v)} /></FormField><FormField label="Actividad predeterminada"><Select value={draft.default_activity_id} items={catalogs.activities} onChange={(v) => { update("default_activity_id", v); update("default_labor_id", ""); }} /></FormField><FormField label="Labor predeterminada"><Select value={draft.default_labor_id} items={labors} onChange={(v) => update("default_labor_id", v)} /></FormField><FormField label="Descripción" wide><textarea rows={3} value={draft.description} onChange={(e) => update("description", e.target.value)} /></FormField></div>;
}
function DriverFields({ draft, update }: { draft: Draft; update: (key: string, value: string) => void }) { return <div className="master-form-grid"><FormField label="Nombre completo *"><Input value={draft.name} onChange={(v) => update("name", v)} /></FormField><FormField label="RUT"><Input placeholder="12.345.678-9" value={draft.rut} onChange={(v) => update("rut", v)} /></FormField><StatusField value={draft.is_active} onChange={(v) => update("is_active", v)} /></div>; }
function NameOnlyFields({ draft, update }: { draft: Draft; update: (key: string, value: string) => void }) { return <div className="master-form-grid"><FormField label="Nombre *"><Input value={draft.name} onChange={(v) => update("name", v)} /></FormField></div>; }
function ImplementFields({ draft, update }: { draft: Draft; update: (key: string, value: string) => void }) { return <div className="master-form-grid"><FormField label="Nombre *"><Input value={draft.name} onChange={(v) => update("name", v)} /></FormField><StatusField value={draft.is_active} onChange={(v) => update("is_active", v)} /></div>; }
function StatusField({ value, onChange }: { value: string; onChange: (value: string) => void }) { return <FormField label="Estado"><select value={value} onChange={(event) => onChange(event.target.value)}><option value="true">Activo</option><option value="false">Inactivo</option></select></FormField>; }
function ActivityFields({ draft, update }: { draft: Draft; update: (key: string, value: string) => void }) { return <div className="master-form-grid"><FormField label="Nombre *"><Input value={draft.name} onChange={(v) => update("name", v)} /></FormField><FormField label="Código"><Input value={draft.code} onChange={(v) => update("code", v)} /></FormField><FormField label="Estado"><select value={draft.is_active} onChange={(e) => update("is_active", e.target.value)}><option value="true">Activa</option><option value="false">Inactiva</option></select></FormField></div>; }
function LaborFields({ draft, catalogs, update }: { draft: Draft; catalogs: Catalogs; update: (key: string, value: string) => void }) { return <div className="master-form-grid"><FormField label="Nombre *"><Input value={draft.name} onChange={(v) => update("name", v)} /></FormField><FormField label="Actividad *"><Select value={draft.activity_id} items={catalogs.activities} empty="Seleccione actividad" onChange={(v) => update("activity_id", v)} /></FormField><FormField label="Código"><Input value={draft.code} onChange={(v) => update("code", v)} /></FormField><FormField label="Factor de esfuerzo"><Input inputMode="decimal" value={draft.effort_factor} onChange={(v) => update("effort_factor", v)} /></FormField><FormField label="Velocidad objetivo (km/h)"><Input inputMode="decimal" value={draft.target_speed_kmh} onChange={(v) => update("target_speed_kmh", v)} /></FormField><FormField label="Estado"><select value={draft.is_active} onChange={(e) => update("is_active", e.target.value)}><option value="true">Activa</option><option value="false">Inactiva</option></select></FormField></div>; }
function CostCenterFields({ draft, update }: { draft: Draft; update: (key: string, value: string) => void }) { return <div className="master-form-grid"><FormField label="Nombre *"><Input value={draft.name} onChange={(v) => update("name", v)} /></FormField><FormField label="Identificador externo"><Input value={draft.external_id} onChange={(v) => update("external_id", v)} /></FormField><FormField label="Superficie (ha)"><Input inputMode="decimal" value={draft.hectares} onChange={(v) => update("hectares", v)} /></FormField><FormField label="Cantidad de hileras"><Input inputMode="numeric" value={draft.row_count} onChange={(v) => update("row_count", v)} /></FormField><FormField label="Cantidad de plantas"><Input inputMode="numeric" value={draft.plant_count} onChange={(v) => update("plant_count", v)} /></FormField></div>; }
function VarietyFields({ draft, catalogs, update }: { draft: Draft; catalogs: Catalogs; update: (key: string, value: string) => void }) { return <div className="master-form-grid"><FormField label="Nombre *"><Input value={draft.name} onChange={(v) => update("name", v)} /></FormField><FormField label="Especie *"><Select value={draft.species_id} items={catalogs.species} empty="Seleccione especie" onChange={(v) => update("species_id", v)} /></FormField></div>; }
function RegionFields({ draft, update }: { draft: Draft; update: (key: string, value: string) => void }) { return <div className="master-form-grid"><FormField label="Nombre *"><Input value={draft.name} onChange={(v) => update("name", v)} /></FormField><FormField label="Código"><Input value={draft.code} onChange={(v) => update("code", v)} /></FormField></div>; }
function CommuneFields({ draft, catalogs, update }: { draft: Draft; catalogs: Catalogs; update: (key: string, value: string) => void }) { return <div className="master-form-grid"><FormField label="Nombre *"><Input value={draft.name} onChange={(v) => update("name", v)} /></FormField><FormField label="Región *"><Select value={draft.region_id} items={catalogs.regions} empty="Seleccione región" onChange={(v) => update("region_id", v)} /></FormField></div>; }
function FundoFields({ draft, catalogs, update }: { draft: Draft; catalogs: Catalogs; update: (key: string, value: string) => void }) { return <div className="master-form-grid"><FormField label="Nombre *"><Input value={draft.name} onChange={(v) => update("name", v)} /></FormField><FormField label="Identificador externo"><Input value={draft.external_id} onChange={(v) => update("external_id", v)} /></FormField><FormField label="Comuna"><Select value={draft.commune_id} items={catalogs.communes} onChange={(v) => update("commune_id", v)} /></FormField><FormField label="Superficie total (ha)"><Input inputMode="decimal" value={draft.hectares_total} onChange={(v) => update("hectares_total", v)} /></FormField><FormField label="Dirección" wide><Input value={draft.address} onChange={(v) => update("address", v)} /></FormField></div>; }
function SectorFields({ draft, catalogs, update }: { draft: Draft; catalogs: Catalogs; update: (key: string, value: string) => void }) { return <div className="master-form-grid"><FormField label="Nombre *"><Input value={draft.name} onChange={(v) => update("name", v)} /></FormField><FormField label="Fundo *"><Select value={draft.fundo_id} items={catalogs.fundos} empty="Seleccione fundo" onChange={(v) => update("fundo_id", v)} /></FormField><FormField label="Identificador externo"><Input value={draft.external_id} onChange={(v) => update("external_id", v)} /></FormField><FormField label="Código SDP"><Input value={draft.sdp_code} onChange={(v) => update("sdp_code", v)} /></FormField><FormField label="Superficie total (ha)"><Input inputMode="decimal" value={draft.hectares_total} onChange={(v) => update("hectares_total", v)} /></FormField></div>; }
function FieldFields({ editorKey, draft, catalogs, update, polygon, setPolygon }: { editorKey: number | string; draft: Draft; catalogs: Catalogs; update: (key: string, value: string) => void; polygon: PolygonPoint[]; setPolygon: (points: PolygonPoint[]) => void }) { return <div className="master-form-grid"><FormField label="Nombre del predio *"><Input value={draft.name} onChange={(v) => update("name", v)} /></FormField><FormField label="Centro de costo"><Select value={draft.cost_center_id} items={catalogs.costCenters} onChange={(v) => update("cost_center_id", v)} /></FormField><FormField label="Color"><input type="color" value={draft.color || "#2f7d5c"} onChange={(e) => update("color", e.target.value)} /></FormField><div className="is-wide"><FieldPolygonEditor key={editorKey} points={polygon} color={draft.color || "#2f7d5c"} onChange={setPolygon} /></div></div>; }
