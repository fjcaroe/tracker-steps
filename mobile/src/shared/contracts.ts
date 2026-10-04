// Contratos tipados entre la app y Odoo (/steps_app/v1). El servidor decide por `error` (código estable), nunca por el texto.
export type DeviceInfo = { uuid: string; platform: string; label?: string; app_version: string };

export type TokenPair = { access_token: string; refresh_token: string; access_expires_at: string; refresh_expires_at: string };

export type MembershipState = 'invited' | 'requested' | 'active' | 'suspended' | 'revoked';
export type Onboarding = 'ready' | 'invitation_pending' | 'request_pending' | 'no_organization';

export type MeOut = {
  ok: true;
  person: { id: number; name: string; email: string | null; state: string };
  email_verified: boolean;
  providers: string[];
  memberships: { org_uid: string; name: string; state: MembershipState }[];
  onboarding: Onboarding;
  device: { id: number };
};

export type CatalogModule = { code: string; name: string; icon: string; contract_version: number; roles: string[]; permissions: string[] };
export type CatalogOut = {
  ok: true;
  server_time: string;
  organization: { org_uid: string; name: string };
  modules: CatalogModule[];
  incompatible_modules: { code: string; server_contract: number; reason: string }[];
  /** Hasta cuándo el teléfono puede operar sin volver a validar permisos. */
  offline_until: string;
};

export type HealthOut = { ok: true; api_version: number; server_time: string; providers: { password: boolean; google: boolean; apple: boolean; test: boolean } };

export type ErrorBody = { ok: false; error: string; message: string; terminal: boolean };

export type DeviceOut = { id: number; label: string | null; platform: string | null; app_version: string | null; last_seen_at: string | null; revoked: boolean; current: boolean };

// ---- Colaciones ----
export type ColacionesMe =
  | { ok: true; linked: false }
  | { ok: true; linked: true; employee: string; eligible: boolean; today: { registered: boolean; registration: string | null; event_datetime: string | null }; recent: { registration: string; meal_date: string; product: string }[] };
export type Totem = { id: number; name: string; code: string; product: string; identification_method: 'barcode' | 'pin' | 'nfc'; allow_offline: boolean; offline_max_hours: number };
export type ColacionRecord = { client_uuid: string; identifier: string; event_datetime: string; offline: boolean };
export type ColacionResult = { client_uuid: string | null; status: 'registered' | 'duplicate' | 'rejected' | 'retry'; message?: string | null; registration?: string; employee?: string; terminal: boolean };

// ---- Movilización ----
export type Trip = {
  id: number; uuid: string; name: string; state: 'draft' | 'open' | 'closed' | 'validated' | 'costed' | 'accounted' | 'cancelled'; date: string;
  scheduled_time: string | null; route: string; direction: string; vehicle: string; capacity: number; aboard_count: number; boarded_count: number; alighted_count: number; overcapacity: boolean;
  events?: { idempotency_key: string; passenger: string; event_type: 'boarding' | 'alighting'; device_datetime: string; state: string; by: string | null }[];
  driver?: string;
};
export type PassengerEvent = { idempotency_key: string; method: 'pin' | 'barcode' | 'nfc' | 'manual'; identifier?: string; passenger_id?: number; event_type: 'boarding' | 'alighting'; device_datetime: string; latitude?: number; longitude?: number; accuracy?: number; location_source?: 'gps' | 'network' | 'manual' };
export type EventResult = { idempotency_key: string | null; status: 'created' | 'duplicate' | 'rejected' | 'retry'; message?: string; terminal: boolean };
