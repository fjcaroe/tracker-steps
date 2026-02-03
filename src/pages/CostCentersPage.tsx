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

  // ========= Cost Center (inline edit) =========
  const [editingCostCenterId, setEditingCostCenterId] = useState<number | null>(null);
  const [selectedCostCenterId, setSelectedCostCenterId] = useState<number | null>(null);
  const [isInlineEditing, setIsInlineEditing] = useState(false);

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

  // ========= Inline create row (new) =========
  const [newCcName, setNewCcName] = useState("");
  const [newCcExternalId, setNewCcExternalId] = useState("");
  const [newCcHectares, setNewCcHectares] = useState("");
  const [newCcFundoId, setNewCcFundoId] = useState<string>("");
  const [newCcSectorId, setNewCcSectorId] = useState<string>("");
  const [newCcRowCount, setNewCcRowCount] = useState<string>("");
  const [newCcPlantCount, setNewCcPlantCount] = useState<string>("");
  const [newCcSpeciesId, setNewCcSpeciesId] = useState<string>("");
  const [newCcVarietyIds, setNewCcVarietyIds] = useState<number[]>([]);
  const [newRowError, setNewRowError] = useState<string | null>(null);

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
  // ========= Fundos (inline table) =========
  const [selectedFundoId, setSelectedFundoId] = useState<number | null>(null);
  const [isInlineEditingFundo, setIsInlineEditingFundo] = useState(false);
  const [fundoInlineError, setFundoInlineError] = useState<string | null>(null);

  // new row (fundo)
  const [newFundoName, setNewFundoName] = useState("");
  const [newFundoExternalId, setNewFundoExternalId] = useState("");
  const [newFundoCommuneId, setNewFundoCommuneId] = useState<string>("");
  const [newFundoAddress, setNewFundoAddress] = useState("");
  const [newFundoHectaresTotal, setNewFundoHectaresTotal] = useState("");
  const [newFundoRowError, setNewFundoRowError] = useState<string | null>(null);

  // ========= Sectors (inline table) =========
  const [selectedSectorId, setSelectedSectorId] = useState<number | null>(null);
  const [isInlineEditingSector, setIsInlineEditingSector] = useState(false);
  const [sectorInlineError, setSectorInlineError] = useState<string | null>(null);

  // new row (sector)
  const [newSectorFundoId, setNewSectorFundoId] = useState<string>("");
  const [newSectorName, setNewSectorName] = useState("");
  const [newSectorSdp, setNewSectorSdp] = useState("");
  const [newSectorExternalId, setNewSectorExternalId] = useState("");
  const [newSectorHectaresTotal, setNewSectorHectaresTotal] = useState("");
  const [newSectorRowError, setNewSectorRowError] = useState<string | null>(null);

  // ========= Species (inline table) =========
  const [selectedSpeciesId, setSelectedSpeciesId] = useState<number | null>(null);
  const [isInlineEditingSpecies, setIsInlineEditingSpecies] = useState(false);
  const [speciesInlineError, setSpeciesInlineError] = useState<string | null>(null);

  // new row (species)
  const [newSpeciesName, setNewSpeciesName] = useState("");
  const [newSpeciesRowError, setNewSpeciesRowError] = useState<string | null>(null);

  // ========= Varieties (inline table) =========
  const [selectedVarietyId, setSelectedVarietyId] = useState<number | null>(null);
  const [isInlineEditingVariety, setIsInlineEditingVariety] = useState(false);
  const [varietyInlineError, setVarietyInlineError] = useState<string | null>(null);

  // new row (variety)
  const [newVarietySpeciesId, setNewVarietySpeciesId] = useState<string>("");
  const [newVarietyName, setNewVarietyName] = useState("");
  const [newVarietyRowError, setNewVarietyRowError] = useState<string | null>(null);

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

  const newSectorsFiltered = useMemo(() => {
    const fundoIdNum = newCcFundoId ? Number(newCcFundoId) : null;
    if (!fundoIdNum) return sectors;
    return sectors.filter((s) => s.fundo_id === fundoIdNum);
  }, [newCcFundoId, sectors]);

  const newVarietiesFiltered = useMemo(() => {
    const spId = newCcSpeciesId ? Number(newCcSpeciesId) : null;
    if (!spId) return varieties;
    return varieties.filter((v) => v.species_id === spId);
  }, [newCcSpeciesId, varieties]);

  const selectedCc = useMemo(
    () => costCenters.find((c) => c.id === selectedCostCenterId) ?? null,
    [costCenters, selectedCostCenterId]
  );
  const selectedFundo = useMemo(
    () => fundos.find((f) => f.id === selectedFundoId) ?? null,
    [fundos, selectedFundoId]
  );

  const selectedSector = useMemo(
    () => sectors.find((s) => s.id === selectedSectorId) ?? null,
    [sectors, selectedSectorId]
  );

  const selectedSpecies = useMemo(
    () => species.find((s) => s.id === selectedSpeciesId) ?? null,
    [species, selectedSpeciesId]
  );

  const selectedVariety = useMemo(
    () => varieties.find((v) => v.id === selectedVarietyId) ?? null,
    [varieties, selectedVarietyId]
  );

  // ========= Loaders =========
  const loadAll = async () => {
    try {
      setLoading(true);
      setError(null);

      const [cc, flds, regs, comms, fnd, secs, sps, vars] = await Promise.all([
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

  useEffect(() => {
    // si el seleccionado ya no existe, limpiar selección
    if (selectedCostCenterId != null && !costCenters.some((c) => c.id === selectedCostCenterId)) {
      setSelectedCostCenterId(null);
      setIsInlineEditing(false);
    }
  }, [costCenters, selectedCostCenterId]);

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
    const fundoId = sectorId ? cc.sector?.fundo_id ?? null : null;

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
      const selectedVarieties = selectedVarietyIds.map((id) => varietyById.get(id)).filter(Boolean) as Variety[];

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

    // PATCH: permitir limpiar variedades => siempre mandar variety_ids en edición
    if (editingCostCenterId != null) {
      body.variety_ids = selectedVarietyIds; // [] limpia
    } else if (selectedVarietyIds.length > 0) {
      body.variety_ids = selectedVarietyIds;
    }

    Object.keys(body).forEach((k) => {
      if (body[k] === undefined) delete body[k];
    });

    return { ok: true as const, body };
  };

  const saveInlineCostCenter = async () => {
    if (editingCostCenterId == null) {
      setSaveError("No hay centro de costo en edición.");
      return;
    }

    const v = validateAndBuildCostCenterBody();
    if (!v.ok) {
      setSaveError(v.error);
      return;
    }

    try {
      setSaving(true);
      setSaveError(null);

      await safeFetchJson(`${apiBaseUrl}/cost_centers/${editingCostCenterId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(v.body),
      });

      setIsInlineEditing(false);
      resetCostCenterForm();
      await loadAll();
    } catch (err: any) {
      console.error(err);
      setSaveError(err?.message || "No se pudo guardar el centro de costo.");
    } finally {
      setSaving(false);
    }
  };

  const resetNewRow = () => {
    setNewCcName("");
    setNewCcExternalId("");
    setNewCcHectares("");
    setNewCcFundoId("");
    setNewCcSectorId("");
    setNewCcRowCount("");
    setNewCcPlantCount("");
    setNewCcSpeciesId("");
    setNewCcVarietyIds([]);
    setNewRowError(null);
  };

  const validateAndBuildNewCostCenterBody = () => {
    if (!newCcName.trim()) return { ok: false as const, error: "El nombre del centro de costo es obligatorio." };

    const hectaresNumber = newCcHectares ? toNumberOrNull(newCcHectares) : null;
    if (newCcHectares && hectaresNumber == null) return { ok: false as const, error: "Las hectáreas deben ser un número." };

    const rowCount = newCcRowCount ? toIntOrNull(newCcRowCount) : null;
    if (newCcRowCount && rowCount == null) return { ok: false as const, error: "Hileras debe ser un número entero." };

    const plantCount = newCcPlantCount ? toIntOrNull(newCcPlantCount) : null;
    if (newCcPlantCount && plantCount == null) return { ok: false as const, error: "Plantas debe ser un número entero." };

    const sectorIdNum = newCcSectorId ? Number(newCcSectorId) : null;
    if (newCcSectorId && Number.isNaN(sectorIdNum)) return { ok: false as const, error: "Sector inválido." };

    // Validación: sector pertenece a fundo (si ambos están)
    const fundoIdNum = newCcFundoId ? Number(newCcFundoId) : null;
    if (sectorIdNum != null && fundoIdNum != null) {
      const sec = sectorById.get(sectorIdNum);
      if (sec && sec.fundo_id !== fundoIdNum) {
        return { ok: false as const, error: "El sector seleccionado no pertenece al fundo seleccionado." };
      }
    }

    // Species / varieties
    const speciesIdNum = newCcSpeciesId ? Number(newCcSpeciesId) : null;
    const selectedVarietyIds = uniq(newCcVarietyIds);

    let finalSpeciesId: number | null = speciesIdNum ?? null;

    if (selectedVarietyIds.length > 0) {
      const selectedVarieties = selectedVarietyIds.map((id) => varietyById.get(id)).filter(Boolean) as Variety[];

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
      name: newCcName.trim(),
      external_id: newCcExternalId.trim() || null,
      sector_id: sectorIdNum ?? null,
      hectares: hectaresNumber,
      row_count: rowCount,
      plant_count: plantCount,
      species_id: finalSpeciesId,
    };

    if (selectedVarietyIds.length > 0) body.variety_ids = selectedVarietyIds;

    Object.keys(body).forEach((k) => {
      if (body[k] === undefined) delete body[k];
    });

    return { ok: true as const, body };
  };
const onSelectFundoRow = (f: Fundo) => {
  if (selectedFundoId === f.id) return;
  setSelectedFundoId(f.id);
  setIsInlineEditingFundo(false);
  setFundoInlineError(null);
  setEditingFundoId(null);
};

const startEditFundoInline = (f: Fundo) => {
  setSelectedFundoId(f.id);
  setEditingFundoId(f.id);
  setIsInlineEditingFundo(true);
  setFundoInlineError(null);

  setFundoName(f.name ?? "");
  setFundoExternalId(f.external_id ?? "");
  setFundoCommuneId(f.commune_id != null ? String(f.commune_id) : "");
  setFundoAddress(f.address ?? "");
  setFundoHectaresTotal(f.hectares_total != null ? String(f.hectares_total) : "");
};
const onSelectSectorRow = (s: Sector) => {
  if (selectedSectorId === s.id) return;
  setSelectedSectorId(s.id);
  setIsInlineEditingSector(false);
  setSectorInlineError(null);
  setEditingSectorId(null);
};

const startEditSectorInline = (s: Sector) => {
  setSelectedSectorId(s.id);
  setEditingSectorId(s.id);
  setIsInlineEditingSector(true);
  setSectorInlineError(null);

  setSectorFundoId(String(s.fundo_id));
  setSectorName(s.name ?? "");
  setSectorSdp(s.sdp_code ?? "");
  setSectorExternalId(s.external_id ?? "");
  setSectorHectaresTotal(s.hectares_total != null ? String(s.hectares_total) : "");
};

const validateAndBuildSectorBody = () => {
  if (!sectorName.trim()) return { ok: false as const, error: "El nombre del sector es obligatorio." };
  if (!sectorFundoId) return { ok: false as const, error: "Debes seleccionar un fundo para el sector." };

  const hectaresTotal = sectorHectaresTotal ? toNumberOrNull(sectorHectaresTotal) : null;
  if (sectorHectaresTotal && hectaresTotal == null) {
    return { ok: false as const, error: "Las hectáreas del sector deben ser un número." };
  }

  const body: any = {
    fundo_id: Number(sectorFundoId),
    name: sectorName.trim(),
    sdp_code: sectorSdp.trim() || null,
    external_id: sectorExternalId.trim() || null,
    hectares_total: hectaresTotal,
  };

  Object.keys(body).forEach((k) => body[k] === undefined && delete body[k]);
  return { ok: true as const, body };
};

const saveInlineSector = async () => {
  if (editingSectorId == null) {
    setSectorInlineError("No hay sector en edición.");
    return;
  }
  const v = validateAndBuildSectorBody();
  if (!v.ok) {
    setSectorInlineError(v.error);
    return;
  }

  try {
    setSaving(true);
    setSectorInlineError(null);

    await safeFetchJson(`${apiBaseUrl}/sectors/${editingSectorId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(v.body),
    });

    setIsInlineEditingSector(false);
    setEditingSectorId(null);
    await reloadCatalogs();
  } catch (err: any) {
    console.error(err);
    setSectorInlineError(err?.message || "No se pudo guardar el sector.");
  } finally {
    setSaving(false);
  }
};

const resetNewSectorRow = () => {
  setNewSectorFundoId("");
  setNewSectorName("");
  setNewSectorSdp("");
  setNewSectorExternalId("");
  setNewSectorHectaresTotal("");
  setNewSectorRowError(null);
};

const validateAndBuildNewSectorBody = () => {
  if (!newSectorName.trim()) return { ok: false as const, error: "El nombre del sector es obligatorio." };
  if (!newSectorFundoId) return { ok: false as const, error: "Debes seleccionar un fundo." };

  const hectaresTotal = newSectorHectaresTotal ? toNumberOrNull(newSectorHectaresTotal) : null;
  if (newSectorHectaresTotal && hectaresTotal == null) {
    return { ok: false as const, error: "Las hectáreas del sector deben ser un número." };
  }

  const body: any = {
    fundo_id: Number(newSectorFundoId),
    name: newSectorName.trim(),
    sdp_code: newSectorSdp.trim() || null,
    external_id: newSectorExternalId.trim() || null,
    hectares_total: hectaresTotal,
  };

  Object.keys(body).forEach((k) => body[k] === undefined && delete body[k]);
  return { ok: true as const, body };
};

const createNewSectorFromRow = async () => {
  const v = validateAndBuildNewSectorBody();
  if (!v.ok) {
    setNewSectorRowError(v.error);
    return;
  }

  try {
    setSaving(true);
    setNewSectorRowError(null);

    await safeFetchJson(`${apiBaseUrl}/sectors`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(v.body),
    });

    resetNewSectorRow();
    await reloadCatalogs();
  } catch (err: any) {
    console.error(err);
    setNewSectorRowError(err?.message || "No se pudo crear el sector.");
  } finally {
    setSaving(false);
  }
};

const deleteSelectedSector = async () => {
  if (!selectedSector) return;
  const ok = window.confirm("¿Eliminar este sector? Puede fallar si tiene centros de costo asociados.");
  if (!ok) return;

  try {
    setSaving(true);
    setError(null);

    await safeFetchJson(`${apiBaseUrl}/sectors/${selectedSector.id}`, { method: "DELETE" });

    if (selectedSectorId === selectedSector.id) setSelectedSectorId(null);
    setIsInlineEditingSector(false);
    setEditingSectorId(null);

    await reloadCatalogs();
  } catch (err: any) {
    console.error(err);
    setError(err?.message || "No se pudo eliminar el sector.");
  } finally {
    setSaving(false);
  }
};

const canAddNewSector = Boolean(newSectorName.trim() && newSectorFundoId);

const onSelectSpeciesRow = (s: Species) => {
  if (selectedSpeciesId === s.id) return;
  setSelectedSpeciesId(s.id);
  setIsInlineEditingSpecies(false);
  setSpeciesInlineError(null);
  setEditingSpeciesId(null);
};

const startEditSpeciesInline = (s: Species) => {
  setSelectedSpeciesId(s.id);
  setEditingSpeciesId(s.id);
  setIsInlineEditingSpecies(true);
  setSpeciesInlineError(null);

  setSpeciesName(s.name ?? "");
};

const validateAndBuildSpeciesBody = () => {
  if (!speciesName.trim()) return { ok: false as const, error: "El nombre de la especie es obligatorio." };
  return { ok: true as const, body: { name: speciesName.trim() } };
};

const saveInlineSpecies = async () => {
  if (editingSpeciesId == null) {
    setSpeciesInlineError("No hay especie en edición.");
    return;
  }
  const v = validateAndBuildSpeciesBody();
  if (!v.ok) {
    setSpeciesInlineError(v.error);
    return;
  }

  try {
    setSaving(true);
    setSpeciesInlineError(null);

    await safeFetchJson(`${apiBaseUrl}/species/${editingSpeciesId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(v.body),
    });

    setIsInlineEditingSpecies(false);
    setEditingSpeciesId(null);
    await reloadCatalogs();
  } catch (err: any) {
    console.error(err);
    setSpeciesInlineError(err?.message || "No se pudo guardar la especie.");
  } finally {
    setSaving(false);
  }
};

const resetNewSpeciesRow = () => {
  setNewSpeciesName("");
  setNewSpeciesRowError(null);
};

const createNewSpeciesFromRow = async () => {
  if (!newSpeciesName.trim()) {
    setNewSpeciesRowError("El nombre de la especie es obligatorio.");
    return;
  }

  try {
    setSaving(true);
    setNewSpeciesRowError(null);

    await safeFetchJson(`${apiBaseUrl}/species`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newSpeciesName.trim() }),
    });

    resetNewSpeciesRow();
    await reloadCatalogs();
  } catch (err: any) {
    console.error(err);
    setNewSpeciesRowError(err?.message || "No se pudo crear la especie.");
  } finally {
    setSaving(false);
  }
};

const deleteSelectedSpecies = async () => {
  if (!selectedSpecies) return;
  const ok = window.confirm("¿Eliminar esta especie? Puede fallar si hay variedades o referencias.");
  if (!ok) return;

  try {
    setSaving(true);
    setError(null);

    await safeFetchJson(`${apiBaseUrl}/species/${selectedSpecies.id}`, { method: "DELETE" });

    if (selectedSpeciesId === selectedSpecies.id) setSelectedSpeciesId(null);
    setIsInlineEditingSpecies(false);
    setEditingSpeciesId(null);

    await reloadCatalogs();
  } catch (err: any) {
    console.error(err);
    setError(err?.message || "No se pudo eliminar la especie.");
  } finally {
    setSaving(false);
  }
};

const canAddNewSpecies = Boolean(newSpeciesName.trim());

const onSelectVarietyRow = (v: Variety) => {
  if (selectedVarietyId === v.id) return;
  setSelectedVarietyId(v.id);
  setIsInlineEditingVariety(false);
  setVarietyInlineError(null);
  setEditingVarietyId(null);
};

const startEditVarietyInline = (v: Variety) => {
  setSelectedVarietyId(v.id);
  setEditingVarietyId(v.id);
  setIsInlineEditingVariety(true);
  setVarietyInlineError(null);

  setVarietyName(v.name ?? "");
  setVarietySpeciesId(String(v.species_id));
};

const validateAndBuildVarietyBody = () => {
  if (!varietyName.trim()) return { ok: false as const, error: "El nombre de la variedad es obligatorio." };
  if (!varietySpeciesId) return { ok: false as const, error: "Debes seleccionar una especie." };

  return {
    ok: true as const,
    body: { name: varietyName.trim(), species_id: Number(varietySpeciesId) },
  };
};

const saveInlineVariety = async () => {
  if (editingVarietyId == null) {
    setVarietyInlineError("No hay variedad en edición.");
    return;
  }
  const v = validateAndBuildVarietyBody();
  if (!v.ok) {
    setVarietyInlineError(v.error);
    return;
  }

  try {
    setSaving(true);
    setVarietyInlineError(null);

    await safeFetchJson(`${apiBaseUrl}/varieties/${editingVarietyId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(v.body),
    });

    setIsInlineEditingVariety(false);
    setEditingVarietyId(null);
    await reloadCatalogs();
  } catch (err: any) {
    console.error(err);
    setVarietyInlineError(err?.message || "No se pudo guardar la variedad.");
  } finally {
    setSaving(false);
  }
};

const resetNewVarietyRow = () => {
  setNewVarietySpeciesId("");
  setNewVarietyName("");
  setNewVarietyRowError(null);
};

const createNewVarietyFromRow = async () => {
  if (!newVarietyName.trim()) {
    setNewVarietyRowError("El nombre de la variedad es obligatorio.");
    return;
  }
  if (!newVarietySpeciesId) {
    setNewVarietyRowError("Debes seleccionar una especie.");
    return;
  }

  try {
    setSaving(true);
    setNewVarietyRowError(null);

    await safeFetchJson(`${apiBaseUrl}/varieties`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newVarietyName.trim(), species_id: Number(newVarietySpeciesId) }),
    });

    resetNewVarietyRow();
    await reloadCatalogs();
  } catch (err: any) {
    console.error(err);
    setNewVarietyRowError(err?.message || "No se pudo crear la variedad.");
  } finally {
    setSaving(false);
  }
};

const deleteSelectedVariety = async () => {
  if (!selectedVariety) return;
  const ok = window.confirm("¿Eliminar esta variedad? Puede fallar si hay referencias.");
  if (!ok) return;

  try {
    setSaving(true);
    setError(null);

    await safeFetchJson(`${apiBaseUrl}/varieties/${selectedVariety.id}`, { method: "DELETE" });

    if (selectedVarietyId === selectedVariety.id) setSelectedVarietyId(null);
    setIsInlineEditingVariety(false);
    setEditingVarietyId(null);

    await reloadCatalogs();
  } catch (err: any) {
    console.error(err);
    setError(err?.message || "No se pudo eliminar la variedad.");
  } finally {
    setSaving(false);
  }
};

const canAddNewVariety = Boolean(newVarietyName.trim() && newVarietySpeciesId);

const validateAndBuildFundoBody = () => {
  if (!fundoName.trim()) return { ok: false as const, error: "El nombre del fundo es obligatorio." };

  const hectaresTotal = fundoHectaresTotal ? toNumberOrNull(fundoHectaresTotal) : null;
  if (fundoHectaresTotal && hectaresTotal == null) {
    return { ok: false as const, error: "Las hectáreas totales del fundo deben ser un número." };
  }

  const body: any = {
    name: fundoName.trim(),
    external_id: fundoExternalId.trim() || null,
    commune_id: fundoCommuneId ? Number(fundoCommuneId) : null,
    address: fundoAddress.trim() || null,
    hectares_total: hectaresTotal,
  };

  Object.keys(body).forEach((k) => body[k] === undefined && delete body[k]);
  return { ok: true as const, body };
};

const saveInlineFundo = async () => {
  if (editingFundoId == null) {
    setFundoInlineError("No hay fundo en edición.");
    return;
  }
  const v = validateAndBuildFundoBody();
  if (!v.ok) {
    setFundoInlineError(v.error);
    return;
  }

  try {
    setSaving(true);
    setFundoInlineError(null);

    await safeFetchJson(`${apiBaseUrl}/fundos/${editingFundoId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(v.body),
    });

    setIsInlineEditingFundo(false);
    setEditingFundoId(null);
    await reloadCatalogs();
  } catch (err: any) {
    console.error(err);
    setFundoInlineError(err?.message || "No se pudo guardar el fundo.");
  } finally {
    setSaving(false);
  }
};

const resetNewFundoRow = () => {
  setNewFundoName("");
  setNewFundoExternalId("");
  setNewFundoCommuneId("");
  setNewFundoAddress("");
  setNewFundoHectaresTotal("");
  setNewFundoRowError(null);
};

const validateAndBuildNewFundoBody = () => {
  if (!newFundoName.trim()) return { ok: false as const, error: "El nombre del fundo es obligatorio." };

  const hectaresTotal = newFundoHectaresTotal ? toNumberOrNull(newFundoHectaresTotal) : null;
  if (newFundoHectaresTotal && hectaresTotal == null) {
    return { ok: false as const, error: "Las hectáreas totales del fundo deben ser un número." };
  }

  const body: any = {
    name: newFundoName.trim(),
    external_id: newFundoExternalId.trim() || null,
    commune_id: newFundoCommuneId ? Number(newFundoCommuneId) : null,
    address: newFundoAddress.trim() || null,
    hectares_total: hectaresTotal,
  };

  Object.keys(body).forEach((k) => body[k] === undefined && delete body[k]);
  return { ok: true as const, body };
};

const createNewFundoFromRow = async () => {
  const v = validateAndBuildNewFundoBody();
  if (!v.ok) {
    setNewFundoRowError(v.error);
    return;
  }

  try {
    setSaving(true);
    setNewFundoRowError(null);

    await safeFetchJson(`${apiBaseUrl}/fundos`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(v.body),
    });

    resetNewFundoRow();
    await reloadCatalogs();
  } catch (err: any) {
    console.error(err);
    setNewFundoRowError(err?.message || "No se pudo crear el fundo.");
  } finally {
    setSaving(false);
  }
};

const deleteSelectedFundo = async () => {
  if (!selectedFundo) return;
  const ok = window.confirm("¿Eliminar este fundo? Puede fallar si tiene sectores asociados.");
  if (!ok) return;

  try {
    setSaving(true);
    setError(null);

    await safeFetchJson(`${apiBaseUrl}/fundos/${selectedFundo.id}`, { method: "DELETE" });

    if (selectedFundoId === selectedFundo.id) setSelectedFundoId(null);
    setIsInlineEditingFundo(false);
    setEditingFundoId(null);

    await reloadCatalogs();
  } catch (err: any) {
    console.error(err);
    setError(err?.message || "No se pudo eliminar el fundo.");
  } finally {
    setSaving(false);
  }
};

const canAddNewFundo = Boolean(newFundoName.trim());

  const createNewCostCenterFromRow = async () => {
    const v = validateAndBuildNewCostCenterBody();
    if (!v.ok) {
      setNewRowError(v.error);
      return;
    }

    try {
      setSaving(true);
      setNewRowError(null);
      setError(null);

      await safeFetchJson(`${apiBaseUrl}/cost_centers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(v.body),
      });

      resetNewRow();
      await loadAll();
    } catch (err: any) {
      console.error(err);
      setNewRowError(err?.message || "No se pudo crear el centro de costo.");
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

  const onSelectRow = (c: CostCenter) => {
    // si ya está seleccionado, no hagas nada (evita cortar la edición al clickear inputs)
    if (selectedCostCenterId === c.id) return;

    setSelectedCostCenterId(c.id);
    setIsInlineEditing(false);
    setSaveError(null);
    resetCostCenterForm();
  };

  const selectedSectorForEdit = ccSectorId ? sectorById.get(Number(ccSectorId)) ?? null : null;
  const selectedSectorForNew = newCcSectorId ? sectorById.get(Number(newCcSectorId)) ?? null : null;

  const canAddNew = Boolean(newCcName.trim());

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
            <div className="sessions-empty">No hay centros de costo aún. Agrega uno en la última fila de la tabla.</div>
          ) : (
            <table className="entity-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Nombre</th>
                  <th>ID externo</th>
                  <th>Fundo</th>
                  <th>Sector</th>
                  <th>SDP</th>
                  <th>Especie</th>
                  <th>Variedades</th>
                  <th>Hectáreas</th>
                  <th>Hileras</th>
                  <th>Plantas</th>
                </tr>
              </thead>

              <tbody>
                {costCenters.map((c) => {
                  const fundo = getFundoFromCostCenter(c);
                  const sector = c.sector ?? null;
                  const spName = c.species_id ? speciesById.get(c.species_id)?.name : null;

                  const isSelected = selectedCostCenterId === c.id;
                  const isEditingThisRow = isInlineEditing && editingCostCenterId === c.id && isSelected;

                  return (
                    <Fragment key={c.id}>
                      <tr
                        onClick={() => onSelectRow(c)}
                        style={{
                          cursor: "pointer",
                          background: isSelected ? "rgba(0,0,0,0.04)" : undefined,
                        }}
                      >
                        <td>{c.id}</td>

                        <td>
                          {isEditingThisRow ? (
                            <input
                              className="form-input"
                              value={ccName}
                              onChange={(e) => setCcName(e.target.value)}
                              placeholder="Nombre"
                            />
                          ) : (
                            c.name
                          )}
                        </td>

                        <td>
                          {isEditingThisRow ? (
                            <input
                              className="form-input"
                              value={ccExternalId}
                              onChange={(e) => setCcExternalId(e.target.value)}
                              placeholder="External ID"
                            />
                          ) : (
                            c.external_id || "—"
                          )}
                        </td>

                        <td>
                          {isEditingThisRow ? (
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
                          ) : (
                            (fundo ? fundo.name : "—")
                          )}
                        </td>

                        <td>
                          {isEditingThisRow ? (
                            <select className="form-input" value={ccSectorId} onChange={(e) => setCcSectorId(e.target.value)}>
                              <option value="">— (sin sector) —</option>
                              {sectorsFilteredForCc.map((s) => (
                                <option key={s.id} value={String(s.id)}>
                                  {s.name}
                                  {s.sdp_code ? ` (SDP: ${s.sdp_code})` : ""}
                                </option>
                              ))}
                            </select>
                          ) : (
                            (sector ? sector.name : "—")
                          )}
                        </td>

                        <td>{(isEditingThisRow ? (selectedSectorForEdit?.sdp_code ?? "—") : (sector?.sdp_code || "—"))}</td>

                        <td>
                          {isEditingThisRow ? (
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
                          ) : (
                            (spName || "—")
                          )}
                        </td>

                        <td>
                          {isEditingThisRow ? (
                            <select
                              className="form-input"
                              multiple
                              value={ccVarietyIds.map(String)}
                              onChange={(e) => {
                                const selected = Array.from(e.target.selectedOptions).map((o) => Number(o.value));
                                setCcVarietyIds(selected);
                              }}
                              style={{ minHeight: 90 }}
                            >
                              {varietiesFilteredForCc.map((v) => (
                                <option key={v.id} value={String(v.id)}>
                                  {v.name}
                                </option>
                              ))}
                            </select>
                          ) : (
                            renderVarieties(c)
                          )}
                        </td>

                        <td>
                          {isEditingThisRow ? (
                            <input
                              className="form-input"
                              value={ccHectares}
                              onChange={(e) => setCcHectares(e.target.value)}
                              placeholder="Ej: 42.5"
                            />
                          ) : (
                            (c.hectares != null ? c.hectares : "—")
                          )}
                        </td>

                        <td>
                          {isEditingThisRow ? (
                            <input
                              className="form-input"
                              value={ccRowCount}
                              onChange={(e) => setCcRowCount(e.target.value)}
                              placeholder="Ej: 80"
                            />
                          ) : (
                            (c.row_count != null ? c.row_count : "—")
                          )}
                        </td>

                        <td>
                          {isEditingThisRow ? (
                            <input
                              className="form-input"
                              value={ccPlantCount}
                              onChange={(e) => setCcPlantCount(e.target.value)}
                              placeholder="Ej: 12000"
                            />
                          ) : (
                            (c.plant_count != null ? c.plant_count : "—")
                          )}
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

                                  const countOrNA = (arr: any[] | null | undefined) => (arr == null ? "No disponible" : String(arr.length));

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
                                              <div>Hectáreas fundo: {fundo.hectares_total != null ? fundo.hectares_total : "—"}</div>
                                            </>
                                          )}

                                          {sector && (
                                            <div>Hectáreas sector: {sector.hectares_total != null ? sector.hectares_total : "—"}</div>
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

                {/* ===== NEW ROW (inline create) ===== */}
                <tr style={{ background: "rgba(0,0,0,0.02)" }}>
                  <td style={{ fontWeight: 700 }}>+</td>

                  <td>
                    <input
                      className="form-input"
                      value={newCcName}
                      onChange={(e) => setNewCcName(e.target.value)}
                      placeholder="Nuevo centro de costo"
                    />
                  </td>

                  <td>
                    <input
                      className="form-input"
                      value={newCcExternalId}
                      onChange={(e) => setNewCcExternalId(e.target.value)}
                      placeholder="External ID"
                    />
                  </td>

                  <td>
                    <select
                      className="form-input"
                      value={newCcFundoId}
                      onChange={(e) => {
                        const next = e.target.value;
                        setNewCcFundoId(next);

                        // si el sector actual no pertenece, lo limpiamos
                        if (newCcSectorId) {
                          const sid = Number(newCcSectorId);
                          const s = sectorById.get(sid);
                          if (s && next && String(s.fundo_id) !== next) setNewCcSectorId("");
                          if (!next) setNewCcSectorId("");
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
                  </td>

                  <td>
                    <select className="form-input" value={newCcSectorId} onChange={(e) => setNewCcSectorId(e.target.value)}>
                      <option value="">— (sin sector) —</option>
                      {newSectorsFiltered.map((s) => (
                        <option key={s.id} value={String(s.id)}>
                          {s.name}
                          {s.sdp_code ? ` (SDP: ${s.sdp_code})` : ""}
                        </option>
                      ))}
                    </select>
                  </td>

                  <td>{selectedSectorForNew?.sdp_code ?? "—"}</td>

                  <td>
                    <select
                      className="form-input"
                      value={newCcSpeciesId}
                      onChange={(e) => {
                        const next = e.target.value;
                        setNewCcSpeciesId(next);

                        if (next) {
                          const spId = Number(next);
                          setNewCcVarietyIds((prev) => prev.filter((id) => varietyById.get(id)?.species_id === spId));
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
                  </td>

                  <td>
                    <select
                      className="form-input"
                      multiple
                      value={newCcVarietyIds.map(String)}
                      onChange={(e) => {
                        const selected = Array.from(e.target.selectedOptions).map((o) => Number(o.value));
                        setNewCcVarietyIds(selected);
                      }}
                      style={{ minHeight: 90 }}
                    >
                      {newVarietiesFiltered.map((v) => (
                        <option key={v.id} value={String(v.id)}>
                          {v.name}
                        </option>
                      ))}
                    </select>
                  </td>

                  <td>
                    <input
                      className="form-input"
                      value={newCcHectares}
                      onChange={(e) => setNewCcHectares(e.target.value)}
                      placeholder="Ej: 42.5"
                    />
                  </td>

                  <td>
                    <input
                      className="form-input"
                      value={newCcRowCount}
                      onChange={(e) => setNewCcRowCount(e.target.value)}
                      placeholder="Ej: 80"
                    />
                  </td>

                  <td>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      <input
                        className="form-input"
                        value={newCcPlantCount}
                        onChange={(e) => setNewCcPlantCount(e.target.value)}
                        placeholder="Ej: 12000"
                      />

                      {canAddNew && (
                        <button
                          type="button"
                          className="form-button-primary"
                          onClick={() => void createNewCostCenterFromRow()}
                          disabled={saving}
                        >
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
            {selectedCc ? (
              <>
                Seleccionado: <b>#{selectedCc.id}</b> — {selectedCc.name}
              </>
            ) : (
              "Selecciona un centro de costo para ver relación / editar / borrar."
            )}
          </div>

          {saveError && <div className="tracker-error">⚠️ {saveError}</div>}
          {newRowError && <div className="tracker-error">⚠️ {newRowError}</div>}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              className="form-button-primary"
              disabled={!selectedCc}
              onClick={() => selectedCc && void toggleRelations(selectedCc.id)}
            >
              {selectedCc && expandedCostCenterId === selectedCc.id ? "Ocultar relación" : "Ver relación"}
            </button>

            {!isInlineEditing ? (
              <button
                type="button"
                className="form-button-primary"
                disabled={!selectedCc}
                onClick={() => {
                  if (!selectedCc) return;
                  setSelectedCostCenterId(selectedCc.id);
                  startEditCostCenter(selectedCc);
                  setIsInlineEditing(true);
                }}
              >
                Editar
              </button>
            ) : (
              <>
                <button type="button" className="form-button-primary" onClick={() => void saveInlineCostCenter()} disabled={saving}>
                  {saving ? "Guardando..." : "Guardar cambios"}
                </button>

                <button
                  type="button"
                  className="form-button-primary"
                  onClick={() => {
                    setIsInlineEditing(false);
                    resetCostCenterForm();
                  }}
                  disabled={saving}
                >
                  Cancelar
                </button>
              </>
            )}

            <button
              type="button"
              className="form-button-primary"
              disabled={!selectedCc || saving}
              onClick={() => selectedCc && void handleDeleteCostCenter(selectedCc.id)}
            >
              Borrar
            </button>
          </div>
        </div>
      </div>

      {/* ========== CATALOGS (same tab) ========== */}
      <div style={{ marginTop: 22 }}>
        <summary style={{ cursor: "pointer", fontWeight: 700 }}>
          Catálogos (Fundo / Sector / Especie / Variedad)
        </summary>

        <div style={{ marginTop: 14, display: "grid", gap: 18 }}>
          {/* Fundos */}
<div className="card" style={{ padding: 12 }}>
  <div style={{ fontWeight: 600, marginBottom: 10 }}>Fundos</div>

  <table className="entity-table">
    <thead>
      <tr>
        <th>ID</th>
        <th>Nombre</th>
        <th>External ID</th>
        <th>Comuna/Región</th>
        <th>Dirección</th>
        <th>Hectáreas</th>
      </tr>
    </thead>

    <tbody>
      {fundos.map((f) => {
        const isSelected = selectedFundoId === f.id;
        const isEditingThisRow = isInlineEditingFundo && editingFundoId === f.id && isSelected;

        return (
          <tr
            key={f.id}
            onClick={() => onSelectFundoRow(f)}
            style={{
              cursor: "pointer",
              background: isSelected ? "rgba(0,0,0,0.04)" : undefined,
            }}
          >
            <td>{f.id}</td>

            <td>
              {isEditingThisRow ? (
                <input className="form-input" value={fundoName} onChange={(e) => setFundoName(e.target.value)} />
              ) : (
                f.name
              )}
            </td>

            <td>
              {isEditingThisRow ? (
                <input className="form-input" value={fundoExternalId} onChange={(e) => setFundoExternalId(e.target.value)} />
              ) : (
                f.external_id || "—"
              )}
            </td>

            <td>
              {isEditingThisRow ? (
                <select className="form-input" value={fundoCommuneId} onChange={(e) => setFundoCommuneId(e.target.value)}>
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
              ) : (
                renderCommuneLabel(f.commune_id ?? null)
              )}
            </td>

            <td>
              {isEditingThisRow ? (
                <input className="form-input" value={fundoAddress} onChange={(e) => setFundoAddress(e.target.value)} />
              ) : (
                f.address || "—"
              )}
            </td>

            <td>
              {isEditingThisRow ? (
                <input
                  className="form-input"
                  value={fundoHectaresTotal}
                  onChange={(e) => setFundoHectaresTotal(e.target.value)}
                  placeholder="Ej: 120.5"
                />
              ) : (
                f.hectares_total != null ? f.hectares_total : "—"
              )}
            </td>
          </tr>
        );
      })}

      {/* NEW ROW */}
      <tr style={{ background: "rgba(0,0,0,0.02)" }}>
        <td style={{ fontWeight: 700 }}>+</td>

        <td>
          <input className="form-input" value={newFundoName} onChange={(e) => setNewFundoName(e.target.value)} placeholder="Nuevo fundo" />
        </td>

        <td>
          <input className="form-input" value={newFundoExternalId} onChange={(e) => setNewFundoExternalId(e.target.value)} placeholder="External ID" />
        </td>

        <td>
          <select className="form-input" value={newFundoCommuneId} onChange={(e) => setNewFundoCommuneId(e.target.value)}>
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
        </td>

        <td>
          <input className="form-input" value={newFundoAddress} onChange={(e) => setNewFundoAddress(e.target.value)} placeholder="Dirección" />
        </td>

        <td>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <input
              className="form-input"
              value={newFundoHectaresTotal}
              onChange={(e) => setNewFundoHectaresTotal(e.target.value)}
              placeholder="Ej: 120.5"
            />

            {canAddNewFundo && (
              <button type="button" className="form-button-primary" onClick={() => void createNewFundoFromRow()} disabled={saving}>
                {saving ? "Agregando..." : "Agregar"}
              </button>
            )}
          </div>
        </td>
      </tr>
    </tbody>
  </table>

  {/* Buttons below */}
  <div style={{ marginTop: 10 }}>
    <div className="card-subtitle" style={{ marginBottom: 8 }}>
      {selectedFundo ? (
        <>
          Seleccionado: <b>#{selectedFundo.id}</b> — {selectedFundo.name}
        </>
      ) : (
        "Selecciona un fundo para editar / borrar."
      )}
    </div>

    {fundoInlineError && <div className="tracker-error">⚠️ {fundoInlineError}</div>}
    {newFundoRowError && <div className="tracker-error">⚠️ {newFundoRowError}</div>}

    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {!isInlineEditingFundo ? (
        <button
          type="button"
          className="form-button-primary"
          disabled={!selectedFundo}
          onClick={() => selectedFundo && startEditFundoInline(selectedFundo)}
        >
          Editar
        </button>
      ) : (
        <>
          <button type="button" className="form-button-primary" onClick={() => void saveInlineFundo()} disabled={saving}>
            {saving ? "Guardando..." : "Guardar cambios"}
          </button>

          <button
            type="button"
            className="form-button-primary"
            onClick={() => {
              setIsInlineEditingFundo(false);
              setEditingFundoId(null);
              setFundoInlineError(null);
            }}
            disabled={saving}
          >
            Cancelar
          </button>
        </>
      )}

      <button type="button" className="form-button-primary" disabled={!selectedFundo || saving} onClick={() => void deleteSelectedFundo()}>
        Borrar
      </button>
    </div>
  </div>
</div>


          {/* Sectors */}

<div className="card" style={{ padding: 12 }}>
  <div style={{ fontWeight: 600, marginBottom: 10 }}>Sectores</div>

  <table className="entity-table">
    <thead>
      <tr>
        <th>ID</th>
        <th>Fundo</th>
        <th>Sector</th>
        <th>SDP</th>
        <th>External ID</th>
        <th>Hectáreas</th>
      </tr>
    </thead>

    <tbody>
      {sectors.map((s) => {
        const isSelected = selectedSectorId === s.id;
        const isEditingThisRow = isInlineEditingSector && editingSectorId === s.id && isSelected;

        return (
          <tr
            key={s.id}
            onClick={() => onSelectSectorRow(s)}
            style={{
              cursor: "pointer",
              background: isSelected ? "rgba(0,0,0,0.04)" : undefined,
            }}
          >
            <td>{s.id}</td>

            <td>
              {isEditingThisRow ? (
                <select className="form-input" value={sectorFundoId} onChange={(e) => setSectorFundoId(e.target.value)}>
                  <option value="">— seleccionar —</option>
                  {fundos.map((f) => (
                    <option key={f.id} value={String(f.id)}>
                      {f.name}
                    </option>
                  ))}
                </select>
              ) : (
                fundoById.get(s.fundo_id)?.name || `#${s.fundo_id}`
              )}
            </td>

            <td>
              {isEditingThisRow ? (
                <input className="form-input" value={sectorName} onChange={(e) => setSectorName(e.target.value)} />
              ) : (
                s.name
              )}
            </td>

            <td>
              {isEditingThisRow ? (
                <input className="form-input" value={sectorSdp} onChange={(e) => setSectorSdp(e.target.value)} placeholder="SDP (SAG)" />
              ) : (
                s.sdp_code || "—"
              )}
            </td>

            <td>
              {isEditingThisRow ? (
                <input className="form-input" value={sectorExternalId} onChange={(e) => setSectorExternalId(e.target.value)} placeholder="External ID" />
              ) : (
                s.external_id || "—"
              )}
            </td>

            <td>
              {isEditingThisRow ? (
                <input
                  className="form-input"
                  value={sectorHectaresTotal}
                  onChange={(e) => setSectorHectaresTotal(e.target.value)}
                  placeholder="Ej: 80"
                />
              ) : (
                s.hectares_total != null ? s.hectares_total : "—"
              )}
            </td>
          </tr>
        );
      })}

      {/* NEW ROW */}
      <tr style={{ background: "rgba(0,0,0,0.02)" }}>
        <td style={{ fontWeight: 700 }}>+</td>

        <td>
          <select className="form-input" value={newSectorFundoId} onChange={(e) => setNewSectorFundoId(e.target.value)}>
            <option value="">— seleccionar —</option>
            {fundos.map((f) => (
              <option key={f.id} value={String(f.id)}>
                {f.name}
              </option>
            ))}
          </select>
        </td>

        <td>
          <input className="form-input" value={newSectorName} onChange={(e) => setNewSectorName(e.target.value)} placeholder="Nuevo sector" />
        </td>

        <td>
          <input className="form-input" value={newSectorSdp} onChange={(e) => setNewSectorSdp(e.target.value)} placeholder="SDP (SAG)" />
        </td>

        <td>
          <input className="form-input" value={newSectorExternalId} onChange={(e) => setNewSectorExternalId(e.target.value)} placeholder="External ID" />
        </td>

        <td>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <input
              className="form-input"
              value={newSectorHectaresTotal}
              onChange={(e) => setNewSectorHectaresTotal(e.target.value)}
              placeholder="Ej: 80"
            />

            {canAddNewSector && (
              <button type="button" className="form-button-primary" onClick={() => void createNewSectorFromRow()} disabled={saving}>
                {saving ? "Agregando..." : "Agregar"}
              </button>
            )}
          </div>
        </td>
      </tr>
    </tbody>
  </table>

  {/* Buttons below */}
  <div style={{ marginTop: 10 }}>
    <div className="card-subtitle" style={{ marginBottom: 8 }}>
      {selectedSector ? (
        <>
          Seleccionado: <b>#{selectedSector.id}</b> — {selectedSector.name}
        </>
      ) : (
        "Selecciona un sector para editar / borrar."
      )}
    </div>

    {sectorInlineError && <div className="tracker-error">⚠️ {sectorInlineError}</div>}
    {newSectorRowError && <div className="tracker-error">⚠️ {newSectorRowError}</div>}

    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {!isInlineEditingSector ? (
        <button
          type="button"
          className="form-button-primary"
          disabled={!selectedSector}
          onClick={() => selectedSector && startEditSectorInline(selectedSector)}
        >
          Editar
        </button>
      ) : (
        <>
          <button type="button" className="form-button-primary" onClick={() => void saveInlineSector()} disabled={saving}>
            {saving ? "Guardando..." : "Guardar cambios"}
          </button>

          <button
            type="button"
            className="form-button-primary"
            onClick={() => {
              setIsInlineEditingSector(false);
              setEditingSectorId(null);
              setSectorInlineError(null);
            }}
            disabled={saving}
          >
            Cancelar
          </button>
        </>
      )}

      <button type="button" className="form-button-primary" disabled={!selectedSector || saving} onClick={() => void deleteSelectedSector()}>
        Borrar
      </button>
    </div>
  </div>
</div>

      {/* Species */}
<div className="card" style={{ padding: 12 }}>
  <div style={{ fontWeight: 600, marginBottom: 10 }}>Especies</div>

  <table className="entity-table">
    <thead>
      <tr>
        <th>ID</th>
        <th>Nombre</th>
      </tr>
    </thead>

    <tbody>
      {species.map((s) => {
        const isSelected = selectedSpeciesId === s.id;
        const isEditingThisRow = isInlineEditingSpecies && editingSpeciesId === s.id && isSelected;

        return (
          <tr
            key={s.id}
            onClick={() => onSelectSpeciesRow(s)}
            style={{
              cursor: "pointer",
              background: isSelected ? "rgba(0,0,0,0.04)" : undefined,
            }}
          >
            <td>{s.id}</td>
            <td>
              {isEditingThisRow ? (
                <input className="form-input" value={speciesName} onChange={(e) => setSpeciesName(e.target.value)} />
              ) : (
                s.name
              )}
            </td>
          </tr>
        );
      })}

      {/* NEW ROW */}
      <tr style={{ background: "rgba(0,0,0,0.02)" }}>
        <td style={{ fontWeight: 700 }}>+</td>
        <td>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <input className="form-input" value={newSpeciesName} onChange={(e) => setNewSpeciesName(e.target.value)} placeholder="Nueva especie" />

            {canAddNewSpecies && (
              <button type="button" className="form-button-primary" onClick={() => void createNewSpeciesFromRow()} disabled={saving}>
                {saving ? "Agregando..." : "Agregar"}
              </button>
            )}
          </div>
        </td>
      </tr>
    </tbody>
  </table>

  {/* Buttons below */}
  <div style={{ marginTop: 10 }}>
    <div className="card-subtitle" style={{ marginBottom: 8 }}>
      {selectedSpecies ? (
        <>
          Seleccionado: <b>#{selectedSpecies.id}</b> — {selectedSpecies.name}
        </>
      ) : (
        "Selecciona una especie para editar / borrar."
      )}
    </div>

    {speciesInlineError && <div className="tracker-error">⚠️ {speciesInlineError}</div>}
    {newSpeciesRowError && <div className="tracker-error">⚠️ {newSpeciesRowError}</div>}

    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {!isInlineEditingSpecies ? (
        <button
          type="button"
          className="form-button-primary"
          disabled={!selectedSpecies}
          onClick={() => selectedSpecies && startEditSpeciesInline(selectedSpecies)}
        >
          Editar
        </button>
      ) : (
        <>
          <button type="button" className="form-button-primary" onClick={() => void saveInlineSpecies()} disabled={saving}>
            {saving ? "Guardando..." : "Guardar cambios"}
          </button>

          <button
            type="button"
            className="form-button-primary"
            onClick={() => {
              setIsInlineEditingSpecies(false);
              setEditingSpeciesId(null);
              setSpeciesInlineError(null);
            }}
            disabled={saving}
          >
            Cancelar
          </button>
        </>
      )}

      <button type="button" className="form-button-primary" disabled={!selectedSpecies || saving} onClick={() => void deleteSelectedSpecies()}>
        Borrar
      </button>
    </div>
  </div>
</div>


  {/* Varieties */}
<div className="card" style={{ padding: 12 }}>
  <div style={{ fontWeight: 600, marginBottom: 10 }}>Variedades</div>

  <table className="entity-table">
    <thead>
      <tr>
        <th>ID</th>
        <th>Especie</th>
        <th>Variedad</th>
      </tr>
    </thead>

    <tbody>
      {varieties.map((v) => {
        const isSelected = selectedVarietyId === v.id;
        const isEditingThisRow = isInlineEditingVariety && editingVarietyId === v.id && isSelected;

        return (
          <tr
            key={v.id}
            onClick={() => onSelectVarietyRow(v)}
            style={{
              cursor: "pointer",
              background: isSelected ? "rgba(0,0,0,0.04)" : undefined,
            }}
          >
            <td>{v.id}</td>

            <td>
              {isEditingThisRow ? (
                <select className="form-input" value={varietySpeciesId} onChange={(e) => setVarietySpeciesId(e.target.value)}>
                  <option value="">— seleccionar —</option>
                  {species.map((s) => (
                    <option key={s.id} value={String(s.id)}>
                      {s.name}
                    </option>
                  ))}
                </select>
              ) : (
                speciesById.get(v.species_id)?.name || `#${v.species_id}`
              )}
            </td>

            <td>
              {isEditingThisRow ? (
                <input className="form-input" value={varietyName} onChange={(e) => setVarietyName(e.target.value)} />
              ) : (
                v.name
              )}
            </td>
          </tr>
        );
      })}

      {/* NEW ROW */}
      <tr style={{ background: "rgba(0,0,0,0.02)" }}>
        <td style={{ fontWeight: 700 }}>+</td>

        <td>
          <select className="form-input" value={newVarietySpeciesId} onChange={(e) => setNewVarietySpeciesId(e.target.value)}>
            <option value="">— seleccionar —</option>
            {species.map((s) => (
              <option key={s.id} value={String(s.id)}>
                {s.name}
              </option>
            ))}
          </select>
        </td>

        <td>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <input className="form-input" value={newVarietyName} onChange={(e) => setNewVarietyName(e.target.value)} placeholder="Nueva variedad" />

            {canAddNewVariety && (
              <button type="button" className="form-button-primary" onClick={() => void createNewVarietyFromRow()} disabled={saving}>
                {saving ? "Agregando..." : "Agregar"}
              </button>
            )}
          </div>
        </td>
      </tr>
    </tbody>
  </table>

  {/* Buttons below */}
  <div style={{ marginTop: 10 }}>
    <div className="card-subtitle" style={{ marginBottom: 8 }}>
      {selectedVariety ? (
        <>
          Seleccionado: <b>#{selectedVariety.id}</b> — {selectedVariety.name}
        </>
      ) : (
        "Selecciona una variedad para editar / borrar."
      )}
    </div>

    {varietyInlineError && <div className="tracker-error">⚠️ {varietyInlineError}</div>}
    {newVarietyRowError && <div className="tracker-error">⚠️ {newVarietyRowError}</div>}

    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {!isInlineEditingVariety ? (
        <button
          type="button"
          className="form-button-primary"
          disabled={!selectedVariety}
          onClick={() => selectedVariety && startEditVarietyInline(selectedVariety)}
        >
          Editar
        </button>
      ) : (
        <>
          <button type="button" className="form-button-primary" onClick={() => void saveInlineVariety()} disabled={saving}>
            {saving ? "Guardando..." : "Guardar cambios"}
          </button>

          <button
            type="button"
            className="form-button-primary"
            onClick={() => {
              setIsInlineEditingVariety(false);
              setEditingVarietyId(null);
              setVarietyInlineError(null);
            }}
            disabled={saving}
          >
            Cancelar
          </button>
        </>
      )}

      <button type="button" className="form-button-primary" disabled={!selectedVariety || saving} onClick={() => void deleteSelectedVariety()}>
        Borrar
      </button>
    </div>
  </div>
</div>

        </div>
      </div>
    </section>
  );
};

export default CostCentersPage;
