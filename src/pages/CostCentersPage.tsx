// src/pages/CostCentersPage.tsx
/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useState, Fragment } from "react";

type Region = { id: number; name: string; code?: string | null };
type Commune = { id: number; region_id: number; name: string };

type Fundo = {
  id: number;
  name: string;
  external_id?: string | null;
  commune_id?: number | null;
  address?: string | null;
  hectares_total?: number | null;
};

type Sector = {
  id: number;
  fundo_id: number;
  name: string;
  external_id?: string | null;
  sdp_code?: string | null;
  hectares_total?: number | null;
};

type Species = { id: number; name: string };
type Variety = { id: number; species_id: number; name: string };

type CostCenter = {
  id: number;
  name: string;
  external_id?: string | null;
  hectares?: number | null;

  sector?: Sector | null;
  row_count?: number | null;
  plant_count?: number | null;

  species_id?: number | null;
  varieties?: Variety[];
};

type FieldOut = {
  id: number;
  name: string;
  cost_center_id?: number | null;
  cost_center_name?: string | null;
  color?: string | null;
  polygon: Array<{ lat: number; lon: number }>;
  created_at: string;

  species_id?: number | null;
  species_name?: string | null;
  variety_id?: number | null;
  variety_name?: string | null;
};

const apiBaseUrl =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) || "http://localhost:8000").replace(
    /\/+$/,
    ""
  );

async function safeFetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Error ${res.status}: ${text}`);
  }
  return (await res.json()) as T;
}

function toNumberOrNull(raw: string): number | null {
  const v = raw.trim();
  if (!v) return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

function toIntOrNull(raw: string): number | null {
  const v = raw.trim();
  if (!v) return null;
  const n = Number(v);
  if (Number.isNaN(n)) return null;
  return Math.trunc(n);
}

function uniq(arr: number[]): number[] {
  return Array.from(new Set(arr));
}

const CostCentersPage = () => {
  // ========= Data stores =========
  const [costCenters, setCostCenters] = useState<CostCenter[]>([]);
  const [fields, setFields] = useState<FieldOut[]>([]);

  const [regions, setRegions] = useState<Region[]>([]);
  const [communes, setCommunes] = useState<Commune[]>([]);
  const [fundos, setFundos] = useState<Fundo[]>([]);
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [species, setSpecies] = useState<Species[]>([]);
  const [varieties, setVarieties] = useState<Variety[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ========= Cost Center form (create/edit) =========
  const [editingCostCenterId, setEditingCostCenterId] = useState<number | null>(null);

  const [ccName, setCcName] = useState("");
  const [ccExternalId, setCcExternalId] = useState("");
  const [ccHectares, setCcHectares] = useState("");

  const [ccFundoId, setCcFundoId] = useState<string>(""); // para filtrar sector
  const [ccSectorId, setCcSectorId] = useState<string>("");

  const [ccRowCount, setCcRowCount] = useState<string>("");
  const [ccPlantCount, setCcPlantCount] = useState<string>("");

  const [ccSpeciesId, setCcSpeciesId] = useState<string>("");
  const [ccVarietyIds, setCcVarietyIds] = useState<number[]>([]);

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // ========= Relations panel =========
  const [expandedCostCenterId, setExpandedCostCenterId] = useState<number | null>(null);
  const [relationsLoading, setRelationsLoading] = useState<Record<number, boolean>>({});
  const [relationsError, setRelationsError] = useState<Record<number, string | null>>({});
  const [relations, setRelations] = useState<
    Record<
      number,
      {
        fields: FieldOut[];
        machines?: any[] | null;
        workOrders?: any[] | null;
        sessions?: any[] | null;
        lots?: any[] | null;
      }
    >
  >({});

  // ========= Catalog forms (simple CRUD inside same tab) =========
  // Fundos
  const [editingFundoId, setEditingFundoId] = useState<number | null>(null);
  const [fundoName, setFundoName] = useState("");
  const [fundoExternalId, setFundoExternalId] = useState("");
  const [fundoCommuneId, setFundoCommuneId] = useState<string>("");
  const [fundoAddress, setFundoAddress] = useState("");
  const [fundoHectaresTotal, setFundoHectaresTotal] = useState("");

  // Sectors
  const [editingSectorId, setEditingSectorId] = useState<number | null>(null);
  const [sectorName, setSectorName] = useState("");
  const [sectorExternalId, setSectorExternalId] = useState("");
  const [sectorFundoId, setSectorFundoId] = useState<string>("");
  const [sectorSdp, setSectorSdp] = useState("");
  const [sectorHectaresTotal, setSectorHectaresTotal] = useState("");

  // Species
  const [editingSpeciesId, setEditingSpeciesId] = useState<number | null>(null);
  const [speciesName, setSpeciesName] = useState("");

  // Varieties
  const [editingVarietyId, setEditingVarietyId] = useState<number | null>(null);
  const [varietyName, setVarietyName] = useState("");
  const [varietySpeciesId, setVarietySpeciesId] = useState<string>("");

  // ========= Memo maps =========
  const regionById = useMemo(() => new Map(regions.map((r) => [r.id, r])), [regions]);
  const communeById = useMemo(() => new Map(communes.map((c) => [c.id, c])), [communes]);
  const fundoById = useMemo(() => new Map(fundos.map((f) => [f.id, f])), [fundos]);
  const sectorById = useMemo(() => new Map(sectors.map((s) => [s.id, s])), [sectors]);
  const speciesById = useMemo(() => new Map(species.map((s) => [s.id, s])), [species]);
  const varietyById = useMemo(() => new Map(varieties.map((v) => [v.id, v])), [varieties]);

  const sectorsFilteredForCc = useMemo(() => {
    const fundoIdNum = ccFundoId ? Number(ccFundoId) : null;
    if (!fundoIdNum) return sectors;
    return sectors.filter((s) => s.fundo_id === fundoIdNum);
  }, [ccFundoId, sectors]);

  const varietiesFilteredForCc = useMemo(() => {
    const spId = ccSpeciesId ? Number(ccSpeciesId) : null;
    if (!spId) return varieties;
    return varieties.filter((v) => v.species_id === spId);
  }, [ccSpeciesId, varieties]);

  // ========= Loaders =========
  const loadAll = async () => {
    try {
      setLoading(true);
      setError(null);

      const [
        cc,
        flds,
        regs,
        comms,
        fnd,
        secs,
        sps,
        vars,
      ] = await Promise.all([
        safeFetchJson<CostCenter[]>(`${apiBaseUrl}/cost_centers`),
        safeFetchJson<FieldOut[]>(`${apiBaseUrl}/fields`).catch(() => [] as FieldOut[]), // no rompe si no está
        safeFetchJson<Region[]>(`${apiBaseUrl}/regions`).catch(() => [] as Region[]),
        safeFetchJson<Commune[]>(`${apiBaseUrl}/communes`).catch(() => [] as Commune[]),
        safeFetchJson<Fundo[]>(`${apiBaseUrl}/fundos`).catch(() => [] as Fundo[]),
        safeFetchJson<Sector[]>(`${apiBaseUrl}/sectors`).catch(() => [] as Sector[]),
        safeFetchJson<Species[]>(`${apiBaseUrl}/species`).catch(() => [] as Species[]),
        safeFetchJson<Variety[]>(`${apiBaseUrl}/varieties`).catch(() => [] as Variety[]),
      ]);

      setCostCenters(cc);
      setFields(flds);

      setRegions(regs);
      setCommunes(comms);
      setFundos(fnd);
      setSectors(secs);
      setSpecies(sps);
      setVarieties(vars);
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "No se pudo cargar la información.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAll();
  }, []);

  // ========= CostCenter helpers =========
  const resetCostCenterForm = () => {
    setEditingCostCenterId(null);
    setCcName("");
    setCcExternalId("");
    setCcHectares("");
    setCcFundoId("");
    setCcSectorId("");
    setCcRowCount("");
    setCcPlantCount("");
    setCcSpeciesId("");
    setCcVarietyIds([]);
    setSaveError(null);
  };

  const startEditCostCenter = (cc: CostCenter) => {
    setEditingCostCenterId(cc.id);
    setSaveError(null);

    setCcName(cc.name ?? "");
    setCcExternalId(cc.external_id ?? "");
    setCcHectares(cc.hectares != null ? String(cc.hectares) : "");

    const sectorId = cc.sector?.id ?? null;
    const fundoId = sectorId ? (cc.sector?.fundo_id ?? null) : null;

    setCcFundoId(fundoId != null ? String(fundoId) : "");
    setCcSectorId(sectorId != null ? String(sectorId) : "");

    setCcRowCount(cc.row_count != null ? String(cc.row_count) : "");
    setCcPlantCount(cc.plant_count != null ? String(cc.plant_count) : "");

    setCcSpeciesId(cc.species_id != null ? String(cc.species_id) : "");
    setCcVarietyIds((cc.varieties ?? []).map((v) => v.id));
  };

  const validateAndBuildCostCenterBody = () => {
    if (!ccName.trim()) return { ok: false as const, error: "El nombre del centro de costo es obligatorio." };

    const hectaresNumber = ccHectares ? toNumberOrNull(ccHectares) : null;
    if (ccHectares && hectaresNumber == null) return { ok: false as const, error: "Las hectáreas deben ser un número." };

    const rowCount = ccRowCount ? toIntOrNull(ccRowCount) : null;
    if (ccRowCount && rowCount == null) return { ok: false as const, error: "Hileras debe ser un número entero." };

    const plantCount = ccPlantCount ? toIntOrNull(ccPlantCount) : null;
    if (ccPlantCount && plantCount == null) return { ok: false as const, error: "Plantas debe ser un número entero." };

    const sectorIdNum = ccSectorId ? Number(ccSectorId) : null;
    if (ccSectorId && Number.isNaN(sectorIdNum)) return { ok: false as const, error: "Sector inválido." };

    // Validación: sector pertenece a fundo (si ambos están)
    const fundoIdNum = ccFundoId ? Number(ccFundoId) : null;
    if (sectorIdNum != null && fundoIdNum != null) {
      const sec = sectorById.get(sectorIdNum);
      if (sec && sec.fundo_id !== fundoIdNum) {
        return { ok: false as const, error: "El sector seleccionado no pertenece al fundo seleccionado." };
      }
    }

    // Species / varieties
    const speciesIdNum = ccSpeciesId ? Number(ccSpeciesId) : null;
    const selectedVarietyIds = uniq(ccVarietyIds);

    let finalSpeciesId: number | null = speciesIdNum ?? null;

    if (selectedVarietyIds.length > 0) {
      const selectedVarieties = selectedVarietyIds
        .map((id) => varietyById.get(id))
        .filter(Boolean) as Variety[];

      if (selectedVarieties.length !== selectedVarietyIds.length) {
        return { ok: false as const, error: "Una o más variedades seleccionadas no existen en catálogo." };
      }

      const speciesIdsFromVar = uniq(selectedVarieties.map((v) => v.species_id));
      if (speciesIdsFromVar.length > 1) {
        return { ok: false as const, error: "Seleccionaste variedades de especies distintas. Ajusta la selección." };
      }

      const derivedSpeciesId = speciesIdsFromVar[0];
      if (finalSpeciesId == null) {
        finalSpeciesId = derivedSpeciesId;
      } else if (finalSpeciesId !== derivedSpeciesId) {
        return { ok: false as const, error: "Las variedades no corresponden a la especie seleccionada." };
      }
    }

    const body: any = {
      name: ccName.trim(),
      external_id: ccExternalId.trim() || null,
      sector_id: sectorIdNum ?? null,
      hectares: hectaresNumber,
      row_count: rowCount,
      plant_count: plantCount,
      species_id: finalSpeciesId,
    };

    // Importante: para PATCH queremos poder limpiar variedades => enviamos siempre variety_ids en edición.
    // Para creación, si está vacío, lo omitimos.
    if (editingCostCenterId != null) {
      body.variety_ids = selectedVarietyIds; // [] limpia
    } else if (selectedVarietyIds.length > 0) {
      body.variety_ids = selectedVarietyIds;
    }

    // Limpieza: no mandar undefined
    Object.keys(body).forEach((k) => {
      if (body[k] === undefined) delete body[k];
    });

    return { ok: true as const, body };
  };

  const handleSubmitCostCenter = async (e: React.FormEvent) => {
    e.preventDefault();

    const v = validateAndBuildCostCenterBody();
    if (!v.ok) {
      setSaveError(v.error);
      return;
    }

    try {
      setSaving(true);
      setSaveError(null);

      const isEdit = editingCostCenterId != null;
      const url = isEdit ? `${apiBaseUrl}/cost_centers/${editingCostCenterId}` : `${apiBaseUrl}/cost_centers`;
      const method = isEdit ? "PATCH" : "POST";

      await safeFetchJson(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(v.body),
      });

      resetCostCenterForm();
      await loadAll();
    } catch (err: any) {
      console.error(err);
      setSaveError(err?.message || "No se pudo guardar el centro de costo.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteCostCenter = async (id: number) => {
    const ok = window.confirm("¿Eliminar este centro de costo? Esta acción no se puede deshacer.");
    if (!ok) return;

    try {
      setSaving(true);
      setError(null);
      await safeFetchJson(`${apiBaseUrl}/cost_centers/${id}`, { method: "DELETE" });
      if (expandedCostCenterId === id) setExpandedCostCenterId(null);
      await loadAll();
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "No se pudo eliminar el centro de costo.");
    } finally {
      setSaving(false);
    }
  };

  // ========= Relations loader =========
  const toggleRelations = async (ccId: number) => {
    if (expandedCostCenterId === ccId) {
      setExpandedCostCenterId(null);
      return;
    }
    setExpandedCostCenterId(ccId);

    // Si ya está cacheado, no recargar
    if (relations[ccId]) return;

    setRelationsLoading((m) => ({ ...m, [ccId]: true }));
    setRelationsError((m) => ({ ...m, [ccId]: null }));

    try {
      const relatedFields = fields.filter((f) => f.cost_center_id === ccId);

      // Endpoints opcionales (si existen)
      const [machines, workOrders, sessions, lots] = await Promise.all([
        safeFetchJson<any[]>(`${apiBaseUrl}/machines`).catch(() => null),
        safeFetchJson<any[]>(`${apiBaseUrl}/work_orders`).catch(() => null),
        safeFetchJson<any[]>(`${apiBaseUrl}/tracking_sessions`).catch(() => null),
        safeFetchJson<any[]>(`${apiBaseUrl}/tracking_lots`).catch(() => null),
      ]);

      const filterByCc = (arr: any[] | null): any[] | null => {
        if (!arr) return null;
        return arr.filter((x) => x?.cost_center_id === ccId);
      };

      setRelations((m) => ({
        ...m,
        [ccId]: {
          fields: relatedFields,
          machines: filterByCc(machines),
          workOrders: filterByCc(workOrders),
          sessions: filterByCc(sessions),
          lots: filterByCc(lots),
        },
      }));
    } catch (err: any) {
      console.error(err);
      setRelationsError((m) => ({ ...m, [ccId]: err?.message || "No se pudieron cargar relaciones." }));
    } finally {
      setRelationsLoading((m) => ({ ...m, [ccId]: false }));
    }
  };

  // ========= Catalog CRUD helpers =========
  const reloadCatalogs = async () => {
    // recarga solo catálogos (sin cost_centers/fields)
    try {
      setLoading(true);
      setError(null);

      const [regs, comms, fnd, secs, sps, vars] = await Promise.all([
        safeFetchJson<Region[]>(`${apiBaseUrl}/regions`).catch(() => [] as Region[]),
        safeFetchJson<Commune[]>(`${apiBaseUrl}/communes`).catch(() => [] as Commune[]),
        safeFetchJson<Fundo[]>(`${apiBaseUrl}/fundos`).catch(() => [] as Fundo[]),
        safeFetchJson<Sector[]>(`${apiBaseUrl}/sectors`).catch(() => [] as Sector[]),
        safeFetchJson<Species[]>(`${apiBaseUrl}/species`).catch(() => [] as Species[]),
        safeFetchJson<Variety[]>(`${apiBaseUrl}/varieties`).catch(() => [] as Variety[]),
      ]);

      setRegions(regs);
      setCommunes(comms);
      setFundos(fnd);
      setSectors(secs);
      setSpecies(sps);
      setVarieties(vars);
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "No se pudieron cargar catálogos.");
    } finally {
      setLoading(false);
    }
  };

  // ===== Fundo CRUD =====
  const resetFundoForm = () => {
    setEditingFundoId(null);
    setFundoName("");
    setFundoExternalId("");
    setFundoCommuneId("");
    setFundoAddress("");
    setFundoHectaresTotal("");
  };

  const submitFundo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fundoName.trim()) {
      setError("El nombre del fundo es obligatorio.");
      return;
    }

    const hectaresTotal = fundoHectaresTotal ? toNumberOrNull(fundoHectaresTotal) : null;
    if (fundoHectaresTotal && hectaresTotal == null) {
      setError("Las hectáreas totales del fundo deben ser un número.");
      return;
    }

    const body: any = {
      name: fundoName.trim(),
      external_id: fundoExternalId.trim() || null,
      commune_id: fundoCommuneId ? Number(fundoCommuneId) : null,
      address: fundoAddress.trim() || null,
      hectares_total: hectaresTotal,
    };

    try {
      setSaving(true);
      setError(null);
      if (editingFundoId == null) {
        await safeFetchJson(`${apiBaseUrl}/fundos`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } else {
        await safeFetchJson(`${apiBaseUrl}/fundos/${editingFundoId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      }
      resetFundoForm();
      await reloadCatalogs();
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "No se pudo guardar el fundo.");
    } finally {
      setSaving(false);
    }
  };

  const editFundo = (f: Fundo) => {
    setEditingFundoId(f.id);
    setFundoName(f.name ?? "");
    setFundoExternalId(f.external_id ?? "");
    setFundoCommuneId(f.commune_id != null ? String(f.commune_id) : "");
    setFundoAddress(f.address ?? "");
    setFundoHectaresTotal(f.hectares_total != null ? String(f.hectares_total) : "");
  };

  const deleteFundo = async (id: number) => {
    const ok = window.confirm("¿Eliminar este fundo? Puede fallar si tiene sectores asociados.");
    if (!ok) return;
    try {
      setSaving(true);
      setError(null);
      await safeFetchJson(`${apiBaseUrl}/fundos/${id}`, { method: "DELETE" });
      if (editingFundoId === id) resetFundoForm();
      await reloadCatalogs();
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "No se pudo eliminar el fundo.");
    } finally {
      setSaving(false);
    }
  };

  // ===== Sector CRUD =====
  const resetSectorForm = () => {
    setEditingSectorId(null);
    setSectorName("");
    setSectorExternalId("");
    setSectorFundoId("");
    setSectorSdp("");
    setSectorHectaresTotal("");
  };

  const submitSector = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sectorName.trim()) {
      setError("El nombre del sector es obligatorio.");
      return;
    }
    if (!sectorFundoId) {
      setError("Debes seleccionar un fundo para el sector.");
      return;
    }
    const hectaresTotal = sectorHectaresTotal ? toNumberOrNull(sectorHectaresTotal) : null;
    if (sectorHectaresTotal && hectaresTotal == null) {
      setError("Las hectáreas del sector deben ser un número.");
      return;
    }

    const body: any = {
      fundo_id: Number(sectorFundoId),
      name: sectorName.trim(),
      external_id: sectorExternalId.trim() || null,
      sdp_code: sectorSdp.trim() || null,
      hectares_total: hectaresTotal,
    };

    try {
      setSaving(true);
      setError(null);

      if (editingSectorId == null) {
        await safeFetchJson(`${apiBaseUrl}/sectors`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } else {
        await safeFetchJson(`${apiBaseUrl}/sectors/${editingSectorId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      }

      resetSectorForm();
      await reloadCatalogs();
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "No se pudo guardar el sector.");
    } finally {
      setSaving(false);
    }
  };

  const editSector = (s: Sector) => {
    setEditingSectorId(s.id);
    setSectorName(s.name ?? "");
    setSectorExternalId(s.external_id ?? "");
    setSectorFundoId(String(s.fundo_id));
    setSectorSdp(s.sdp_code ?? "");
    setSectorHectaresTotal(s.hectares_total != null ? String(s.hectares_total) : "");
  };

  const deleteSector = async (id: number) => {
    const ok = window.confirm("¿Eliminar este sector? Puede fallar si tiene centros de costo asociados.");
    if (!ok) return;
    try {
      setSaving(true);
      setError(null);
      await safeFetchJson(`${apiBaseUrl}/sectors/${id}`, { method: "DELETE" });
      if (editingSectorId === id) resetSectorForm();
      await reloadCatalogs();
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "No se pudo eliminar el sector.");
    } finally {
      setSaving(false);
    }
  };

  // ===== Species CRUD =====
  const resetSpeciesForm = () => {
    setEditingSpeciesId(null);
    setSpeciesName("");
  };

  const submitSpecies = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!speciesName.trim()) {
      setError("El nombre de la especie es obligatorio.");
      return;
    }
    const body = { name: speciesName.trim() };
    try {
      setSaving(true);
      setError(null);

      if (editingSpeciesId == null) {
        await safeFetchJson(`${apiBaseUrl}/species`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } else {
        await safeFetchJson(`${apiBaseUrl}/species/${editingSpeciesId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      }

      resetSpeciesForm();
      await reloadCatalogs();
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "No se pudo guardar la especie.");
    } finally {
      setSaving(false);
    }
  };

  const editSpecies = (s: Species) => {
    setEditingSpeciesId(s.id);
    setSpeciesName(s.name ?? "");
  };

  const deleteSpecies = async (id: number) => {
    const ok = window.confirm("¿Eliminar esta especie? Puede fallar si hay variedades o referencias.");
    if (!ok) return;
    try {
      setSaving(true);
      setError(null);
      await safeFetchJson(`${apiBaseUrl}/species/${id}`, { method: "DELETE" });
      if (editingSpeciesId === id) resetSpeciesForm();
      await reloadCatalogs();
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "No se pudo eliminar la especie.");
    } finally {
      setSaving(false);
    }
  };

  // ===== Varieties CRUD =====
  const resetVarietyForm = () => {
    setEditingVarietyId(null);
    setVarietyName("");
    setVarietySpeciesId("");
  };

  const submitVariety = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!varietyName.trim()) {
      setError("El nombre de la variedad es obligatorio.");
      return;
    }
    if (!varietySpeciesId) {
      setError("Debes seleccionar una especie para la variedad.");
      return;
    }
    const body: any = { name: varietyName.trim(), species_id: Number(varietySpeciesId) };

    try {
      setSaving(true);
      setError(null);

      if (editingVarietyId == null) {
        await safeFetchJson(`${apiBaseUrl}/varieties`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } else {
        await safeFetchJson(`${apiBaseUrl}/varieties/${editingVarietyId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      }

      resetVarietyForm();
      await reloadCatalogs();
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "No se pudo guardar la variedad.");
    } finally {
      setSaving(false);
    }
  };

  const editVariety = (v: Variety) => {
    setEditingVarietyId(v.id);
    setVarietyName(v.name ?? "");
    setVarietySpeciesId(String(v.species_id));
  };

  const deleteVariety = async (id: number) => {
    const ok = window.confirm("¿Eliminar esta variedad? Puede fallar si hay referencias.");
    if (!ok) return;
    try {
      setSaving(true);
      setError(null);
      await safeFetchJson(`${apiBaseUrl}/varieties/${id}`, { method: "DELETE" });
      if (editingVarietyId === id) resetVarietyForm();
      await reloadCatalogs();
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "No se pudo eliminar la variedad.");
    } finally {
      setSaving(false);
    }
  };

  // ========= Render helpers =========
  const renderCommuneLabel = (communeId?: number | null) => {
    if (!communeId) return "—";
    const c = communeById.get(communeId);
    if (!c) return `#${communeId}`;
    const r = regionById.get(c.region_id);
    return r ? `${c.name} (${r.name})` : c.name;
  };

  const getFundoFromCostCenter = (cc: CostCenter): Fundo | null => {
    const sec = cc.sector;
    if (!sec) return null;
    return fundoById.get(sec.fundo_id) ?? null;
  };

  const renderVarieties = (cc: CostCenter) => {
    const v = cc.varieties ?? [];
    if (v.length === 0) return "—";
    return v.map((x) => x.name).join(", ");
  };

  return (
    <section className="card entity-page">
      {/* Header */}
      <div className="card-header cc-header">
      <div className="cc-header__text">
        <div className="card-title">Centros de costo</div>
        <div className="card-subtitle">
          Administración completa: Centro de costo, relación con Fundo/Sector (SDP) y catálogos de especie/variedad.
        </div>
      </div>
    </div>

    {/* Global error */}
    {error && <div className="tracker-error">⚠️ {error}</div>}

      {/* ========== COST CENTER TABLE ========== */}
       <div className="cc-section cc-section--table">
      <div className="cc-section__top">
        <div className="cc-section__title">Listado</div>
      </div>

        <div className="entity-table-wrapper cc-table-full">
          {loading ? (
            <div className="sessions-loading">Cargando…</div>
          ) : costCenters.length === 0 ? (
            <div className="sessions-empty">No hay centros de costo aún. Crea uno con el formulario.</div>
          ) : (
            <table className="entity-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Nombre</th>
                  <th>Fundo</th>
                  <th>Sector</th>
                  <th>SDP</th>
                  <th>Especie</th>
                  <th>Variedades</th>
                  <th>Hectáreas</th>
                  <th>Hileras</th>
                  <th>Plantas</th>
                  <th style={{ minWidth: 220 }}>Acciones</th>
                </tr>
              </thead>
<tbody>
  {costCenters.map((c) => {
    const fundo = getFundoFromCostCenter(c);
    const sector = c.sector ?? null;
    const spName = c.species_id ? speciesById.get(c.species_id)?.name : null;

    return (
      <Fragment key={c.id}>
        <tr>
          <td>{c.id}</td>
          <td>{c.name}</td>
          <td>{fundo ? fundo.name : "—"}</td>
          <td>{sector ? sector.name : "—"}</td>
          <td>{sector?.sdp_code || "—"}</td>
          <td>{spName || "—"}</td>
          <td>{renderVarieties(c)}</td>
          <td>{c.hectares != null ? c.hectares : "—"}</td>
          <td>{c.row_count != null ? c.row_count : "—"}</td>
          <td>{c.plant_count != null ? c.plant_count : "—"}</td>
          <td>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button
                type="button"
                className="form-button-primary"
                onClick={() => void toggleRelations(c.id)}
              >
                {expandedCostCenterId === c.id ? "Ocultar relación" : "Ver relación"}
              </button>

              <button
                type="button"
                className="form-button-primary"
                onClick={() => startEditCostCenter(c)}
              >
                Editar
              </button>

              <button
                type="button"
                className="form-button-primary"
                onClick={() => void handleDeleteCostCenter(c.id)}
                disabled={saving}
              >
                Borrar
              </button>
            </div>
          </td>
        </tr>

        {expandedCostCenterId === c.id && (
          <tr>
            <td colSpan={11} style={{ background: "rgba(0,0,0,0.02)" }}>
              <div style={{ padding: 12 }}>
                {relationsLoading[c.id] ? (
                  <div className="sessions-loading">Cargando relaciones…</div>
                ) : relationsError[c.id] ? (
                  <div className="tracker-error">⚠️ {relationsError[c.id]}</div>
                ) : (
                  (() => {
                    const rel = relations[c.id] ?? {
                      fields: fields.filter((f) => f.cost_center_id === c.id),
                    };

                    const countOrNA = (arr: any[] | null | undefined) =>
                      arr == null ? "No disponible" : String(arr.length);

                    return (
                      <>
                        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 10 }}>
                          <div>
                            <div style={{ fontWeight: 600 }}>Resumen</div>
                            <div>Cuarteles: {rel.fields.length}</div>
                            <div>Máquinas: {countOrNA(rel.machines)}</div>
                            <div>Órdenes de trabajo: {countOrNA(rel.workOrders)}</div>
                            <div>Sesiones: {countOrNA(rel.sessions)}</div>
                            <div>Lotes: {countOrNA(rel.lots)}</div>
                          </div>

                          <div>
                            <div style={{ fontWeight: 600 }}>Detalle Centro de costo</div>
                            <div>Fundo: {fundo ? fundo.name : "—"}</div>
                            <div>Sector: {sector ? sector.name : "—"}</div>
                            <div>SDP: {sector?.sdp_code || "—"}</div>

                            {fundo && (
                              <>
                                <div>Comuna/Región: {renderCommuneLabel(fundo.commune_id ?? null)}</div>
                                <div>Dirección: {fundo.address || "—"}</div>
                                <div>
                                  Hectáreas fundo: {fundo.hectares_total != null ? fundo.hectares_total : "—"}
                                </div>
                              </>
                            )}

                            {sector && (
                              <div>
                                Hectáreas sector: {sector.hectares_total != null ? sector.hectares_total : "—"}
                              </div>
                            )}
                          </div>
                        </div>

                        <div style={{ fontWeight: 600, marginBottom: 6 }}>Cuarteles (Fields)</div>

                        {rel.fields.length === 0 ? (
                          <div className="sessions-empty">No hay cuarteles asociados a este centro de costo.</div>
                        ) : (
                          <table className="entity-table" style={{ marginTop: 8 }}>
                            <thead>
                              <tr>
                                <th>ID</th>
                                <th>Nombre</th>
                                <th>Especie</th>
                                <th>Variedad</th>
                                <th>Color</th>
                                <th>Creado</th>
                              </tr>
                            </thead>
                            <tbody>
                              {rel.fields.map((f) => (
                                <tr key={f.id}>
                                  <td>{f.id}</td>
                                  <td>{f.name}</td>
                                  <td>{f.species_name || (f.species_id ? `#${f.species_id}` : "—")}</td>
                                  <td>{f.variety_name || (f.variety_id ? `#${f.variety_id}` : "—")}</td>
                                  <td>{f.color || "—"}</td>
                                  <td>{f.created_at ? new Date(f.created_at).toLocaleString() : "—"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </>
                    );
                  })()
                )}
              </div>
            </td>
          </tr>
        )}
      </Fragment>
    );
  })}
</tbody>

            </table>
          )}
        </div>
      </div>
+

    {/* ========== COST CENTER FORM ========== */}
    <div className="cc-section">
      <div className="cc-section__top">
        <div className="cc-section__title">
          {editingCostCenterId == null ? "Crear centro de costo" : `Editando centro de costo #${editingCostCenterId}`}
        </div>

        {editingCostCenterId != null && (
          <button type="button" className="form-button-primary" onClick={resetCostCenterForm} disabled={saving}>
            Cancelar edición
          </button>
        )}
      </div>

        <form className="form-grid" onSubmit={handleSubmitCostCenter} style={{ marginTop: 10 }}>
          <div className="form-field">
            <label className="form-label">Nombre centro de costo *</label>
            <input
              className="form-input"
              value={ccName}
              onChange={(e) => setCcName(e.target.value)}
              placeholder="Ej: Cuartel 12 - Norte"
            />
          </div>

          <div className="form-field">
            <label className="form-label">ID externo (Odoo / ERP)</label>
            <input
              className="form-input"
              value={ccExternalId}
              onChange={(e) => setCcExternalId(e.target.value)}
              placeholder="Código en Odoo u otro sistema"
            />
          </div>

          <div className="form-field">
            <label className="form-label">Hectáreas (opcional)</label>
            <input
              className="form-input"
              value={ccHectares}
              onChange={(e) => setCcHectares(e.target.value)}
              placeholder="Ej: 42.5"
            />
          </div>

          <div className="form-field">
            <label className="form-label">Fundo (para filtrar sectores)</label>
            <select
              className="form-input"
              value={ccFundoId}
              onChange={(e) => {
                const next = e.target.value;
                setCcFundoId(next);

                // si el sector actual no pertenece, lo limpiamos
                if (ccSectorId) {
                  const sid = Number(ccSectorId);
                  const s = sectorById.get(sid);
                  if (s && next && String(s.fundo_id) !== next) setCcSectorId("");
                  if (!next) setCcSectorId("");
                }
              }}
            >
              <option value="">— (sin fundo) —</option>
              {fundos.map((f) => (
                <option key={f.id} value={String(f.id)}>
                  {f.name}
                </option>
              ))}
            </select>
          </div>

          <div className="form-field">
            <label className="form-label">Sector (SDP)</label>
            <select
              className="form-input"
              value={ccSectorId}
              onChange={(e) => setCcSectorId(e.target.value)}
            >
              <option value="">— (sin sector) —</option>
              {sectorsFilteredForCc.map((s) => (
                <option key={s.id} value={String(s.id)}>
                  {s.name}
                  {s.sdp_code ? ` (SDP: ${s.sdp_code})` : ""}
                </option>
              ))}
            </select>
          </div>

          <div className="form-field">
            <label className="form-label">Hileras (opcional)</label>
            <input
              className="form-input"
              value={ccRowCount}
              onChange={(e) => setCcRowCount(e.target.value)}
              placeholder="Ej: 80"
            />
          </div>

          <div className="form-field">
            <label className="form-label">Plantas (opcional)</label>
            <input
              className="form-input"
              value={ccPlantCount}
              onChange={(e) => setCcPlantCount(e.target.value)}
              placeholder="Ej: 12000"
            />
          </div>

          <div className="form-field">
            <label className="form-label">Especie (opcional)</label>
            <select
              className="form-input"
              value={ccSpeciesId}
              onChange={(e) => {
                const next = e.target.value;
                setCcSpeciesId(next);
                // si cambió especie, filtrar variedades seleccionadas a las válidas
                if (next) {
                  const spId = Number(next);
                  setCcVarietyIds((prev) => prev.filter((id) => varietyById.get(id)?.species_id === spId));
                }
              }}
            >
              <option value="">— (sin especie) —</option>
              {species.map((s) => (
                <option key={s.id} value={String(s.id)}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          <div className="form-field" style={{ gridColumn: "1 / -1" }}>
            <label className="form-label">Variedades (multi selección, opcional)</label>
            <select
              className="form-input"
              multiple
              value={ccVarietyIds.map(String)}
              onChange={(e) => {
                const selected = Array.from(e.target.selectedOptions).map((o) => Number(o.value));
                setCcVarietyIds(selected);
              }}
              style={{ minHeight: 110 }}
            >
              {varietiesFilteredForCc.map((v) => (
                <option key={v.id} value={String(v.id)}>
                  {v.name}
                </option>
              ))}
            </select>
            <div className="card-subtitle" style={{ marginTop: 6 }}>
              Si seleccionas variedades, se validará coherencia con la especie. Si no eliges especie, se derivará desde la variedad.
            </div>
          </div>

          {saveError && <div className="tracker-error">⚠️ {saveError}</div>}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="submit" className="form-button-primary" disabled={saving}>
              {saving ? "Guardando..." : editingCostCenterId == null ? "Agregar centro de costo" : "Guardar cambios"}
            </button>

            {editingCostCenterId == null && (
              <button type="button" className="form-button-primary" disabled={saving} onClick={resetCostCenterForm}>
                Limpiar
              </button>
            )}
          </div>
        </form>
      </div>


      {/* ========== CATALOGS (same tab) ========== */}
      <div style={{ marginTop: 22 }}>
          <summary style={{ cursor: "pointer", fontWeight: 700 }}>Catálogos (Fundo / Sector / Especie / Variedad)</summary>

          <div style={{ marginTop: 14, display: "grid", gap: 18 }}>
            {/* Fundos */}
            <div className="card" style={{ padding: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <div style={{ fontWeight: 600 }}>
                  {editingFundoId == null ? "Fundos (crear)" : `Fundos (editando #${editingFundoId})`}
                </div>
                {editingFundoId != null && (
                  <button type="button" className="form-button-primary" onClick={resetFundoForm} disabled={saving}>
                    Cancelar
                  </button>
                )}
              </div>

              <form className="form-grid" onSubmit={submitFundo} style={{ marginTop: 10 }}>
                <div className="form-field">
                  <label className="form-label">Nombre fundo *</label>
                  <input className="form-input" value={fundoName} onChange={(e) => setFundoName(e.target.value)} />
                </div>
                <div className="form-field">
                  <label className="form-label">External ID</label>
                  <input
                    className="form-input"
                    value={fundoExternalId}
                    onChange={(e) => setFundoExternalId(e.target.value)}
                  />
                </div>
                <div className="form-field">
                  <label className="form-label">Comuna</label>
                  <select
                    className="form-input"
                    value={fundoCommuneId}
                    onChange={(e) => setFundoCommuneId(e.target.value)}
                  >
                    <option value="">— (sin comuna) —</option>
                    {communes.map((c) => {
                      const r = regionById.get(c.region_id);
                      return (
                        <option key={c.id} value={String(c.id)}>
                          {c.name}
                          {r ? ` (${r.name})` : ""}
                        </option>
                      );
                    })}
                  </select>
                </div>
                <div className="form-field">
                  <label className="form-label">Dirección</label>
                  <input className="form-input" value={fundoAddress} onChange={(e) => setFundoAddress(e.target.value)} />
                </div>
                <div className="form-field">
                  <label className="form-label">Hectáreas totales</label>
                  <input
                    className="form-input"
                    value={fundoHectaresTotal}
                    onChange={(e) => setFundoHectaresTotal(e.target.value)}
                    placeholder="Ej: 120.5"
                  />
                </div>

                <div>
                  <button type="submit" className="form-button-primary" disabled={saving}>
                    {saving ? "Guardando..." : editingFundoId == null ? "Agregar fundo" : "Guardar cambios"}
                  </button>
                </div>
              </form>

              <div style={{ marginTop: 10 }}>
                <table className="entity-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Nombre</th>
                      <th>Comuna/Región</th>
                      <th>Hectáreas</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fundos.map((f) => (
                      <tr key={f.id}>
                        <td>{f.id}</td>
                        <td>{f.name}</td>
                        <td>{renderCommuneLabel(f.commune_id ?? null)}</td>
                        <td>{f.hectares_total != null ? f.hectares_total : "—"}</td>
                        <td>
                          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                            <button type="button" className="form-button-primary" onClick={() => editFundo(f)}>
                              Editar
                            </button>
                            <button
                              type="button"
                              className="form-button-primary"
                              onClick={() => void deleteFundo(f.id)}
                              disabled={saving}
                            >
                              Borrar
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {fundos.length === 0 && (
                      <tr>
                        <td colSpan={5}>—</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Sectors */}
            <div className="card" style={{ padding: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <div style={{ fontWeight: 600 }}>
                  {editingSectorId == null ? "Sectores (crear)" : `Sectores (editando #${editingSectorId})`}
                </div>
                {editingSectorId != null && (
                  <button type="button" className="form-button-primary" onClick={resetSectorForm} disabled={saving}>
                    Cancelar
                  </button>
                )}
              </div>

              <form className="form-grid" onSubmit={submitSector} style={{ marginTop: 10 }}>
                <div className="form-field">
                  <label className="form-label">Fundo *</label>
                  <select
                    className="form-input"
                    value={sectorFundoId}
                    onChange={(e) => setSectorFundoId(e.target.value)}
                  >
                    <option value="">— seleccionar —</option>
                    {fundos.map((f) => (
                      <option key={f.id} value={String(f.id)}>
                        {f.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-field">
                  <label className="form-label">Nombre sector *</label>
                  <input className="form-input" value={sectorName} onChange={(e) => setSectorName(e.target.value)} />
                </div>

                <div className="form-field">
                  <label className="form-label">SDP (SAG)</label>
                  <input className="form-input" value={sectorSdp} onChange={(e) => setSectorSdp(e.target.value)} />
                </div>

                <div className="form-field">
                  <label className="form-label">External ID</label>
                  <input
                    className="form-input"
                    value={sectorExternalId}
                    onChange={(e) => setSectorExternalId(e.target.value)}
                  />
                </div>

                <div className="form-field">
                  <label className="form-label">Hectáreas totales</label>
                  <input
                    className="form-input"
                    value={sectorHectaresTotal}
                    onChange={(e) => setSectorHectaresTotal(e.target.value)}
                    placeholder="Ej: 80"
                  />
                </div>

                <div>
                  <button type="submit" className="form-button-primary" disabled={saving}>
                    {saving ? "Guardando..." : editingSectorId == null ? "Agregar sector" : "Guardar cambios"}
                  </button>
                </div>
              </form>

              <div style={{ marginTop: 10 }}>
                <table className="entity-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Fundo</th>
                      <th>Sector</th>
                      <th>SDP</th>
                      <th>Hectáreas</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sectors.map((s) => (
                      <tr key={s.id}>
                        <td>{s.id}</td>
                        <td>{fundoById.get(s.fundo_id)?.name || `#${s.fundo_id}`}</td>
                        <td>{s.name}</td>
                        <td>{s.sdp_code || "—"}</td>
                        <td>{s.hectares_total != null ? s.hectares_total : "—"}</td>
                        <td>
                          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                            <button type="button" className="form-button-primary" onClick={() => editSector(s)}>
                              Editar
                            </button>
                            <button
                              type="button"
                              className="form-button-primary"
                              onClick={() => void deleteSector(s.id)}
                              disabled={saving}
                            >
                              Borrar
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {sectors.length === 0 && (
                      <tr>
                        <td colSpan={6}>—</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Species */}
            <div className="card" style={{ padding: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <div style={{ fontWeight: 600 }}>
                  {editingSpeciesId == null ? "Especies (crear)" : `Especies (editando #${editingSpeciesId})`}
                </div>
                {editingSpeciesId != null && (
                  <button type="button" className="form-button-primary" onClick={resetSpeciesForm} disabled={saving}>
                    Cancelar
                  </button>
                )}
              </div>

              <form className="form-grid" onSubmit={submitSpecies} style={{ marginTop: 10 }}>
                <div className="form-field">
                  <label className="form-label">Nombre especie *</label>
                  <input className="form-input" value={speciesName} onChange={(e) => setSpeciesName(e.target.value)} />
                </div>
                <div>
                  <button type="submit" className="form-button-primary" disabled={saving}>
                    {saving ? "Guardando..." : editingSpeciesId == null ? "Agregar especie" : "Guardar cambios"}
                  </button>
                </div>
              </form>

              <div style={{ marginTop: 10 }}>
                <table className="entity-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Nombre</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {species.map((s) => (
                      <tr key={s.id}>
                        <td>{s.id}</td>
                        <td>{s.name}</td>
                        <td>
                          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                            <button type="button" className="form-button-primary" onClick={() => editSpecies(s)}>
                              Editar
                            </button>
                            <button
                              type="button"
                              className="form-button-primary"
                              onClick={() => void deleteSpecies(s.id)}
                              disabled={saving}
                            >
                              Borrar
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {species.length === 0 && (
                      <tr>
                        <td colSpan={3}>—</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Varieties */}
            <div className="card" style={{ padding: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <div style={{ fontWeight: 600 }}>
                  {editingVarietyId == null ? "Variedades (crear)" : `Variedades (editando #${editingVarietyId})`}
                </div>
                {editingVarietyId != null && (
                  <button type="button" className="form-button-primary" onClick={resetVarietyForm} disabled={saving}>
                    Cancelar
                  </button>
                )}
              </div>

              <form className="form-grid" onSubmit={submitVariety} style={{ marginTop: 10 }}>
                <div className="form-field">
                  <label className="form-label">Especie *</label>
                  <select
                    className="form-input"
                    value={varietySpeciesId}
                    onChange={(e) => setVarietySpeciesId(e.target.value)}
                  >
                    <option value="">— seleccionar —</option>
                    {species.map((s) => (
                      <option key={s.id} value={String(s.id)}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-field">
                  <label className="form-label">Nombre variedad *</label>
                  <input className="form-input" value={varietyName} onChange={(e) => setVarietyName(e.target.value)} />
                </div>

                <div>
                  <button type="submit" className="form-button-primary" disabled={saving}>
                    {saving ? "Guardando..." : editingVarietyId == null ? "Agregar variedad" : "Guardar cambios"}
                  </button>
                </div>
              </form>

              <div style={{ marginTop: 10 }}>
                <table className="entity-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Especie</th>
                      <th>Variedad</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {varieties.map((v) => (
                      <tr key={v.id}>
                        <td>{v.id}</td>
                        <td>{speciesById.get(v.species_id)?.name || `#${v.species_id}`}</td>
                        <td>{v.name}</td>
                        <td>
                          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                            <button type="button" className="form-button-primary" onClick={() => editVariety(v)}>
                              Editar
                            </button>
                            <button
                              type="button"
                              className="form-button-primary"
                              onClick={() => void deleteVariety(v.id)}
                              disabled={saving}
                            >
                              Borrar
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {varieties.length === 0 && (
                      <tr>
                        <td colSpan={4}>—</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
      </div>
    </section>
  );
};

export default CostCentersPage;
