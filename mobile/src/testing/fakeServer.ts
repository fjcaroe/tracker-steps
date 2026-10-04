// Servidor FALSO que implementa el contrato /steps_app/v1 en memoria. Sirve para probar el cliente (recorridos, fallos de red, revocación).
// NO es evidencia de que Odoo funcione: la lógica real vive en step_mobile_portal* y se prueba con sus propias pruebas Odoo.
type Json = Record<string, unknown>;
type Grant = { module: string; role: string; revokedAt?: number; scope?: number[] };
type Membership = { personId: number; orgUid: string; state: string; partner?: number; employee?: number; grants: Grant[]; endedAt?: number };
type Session = { personId: number; deviceUuid: string; access: string; refresh: string; prevRefresh?: string; accessExp: number; revoked?: boolean };

const PERMS: Record<string, Record<string, string[]>> = {
  colaciones: { persona: ['colaciones.read_own'], operador: ['colaciones.register'] },
  mobilization: { conductor: ['mobilization.drive'], supervisor: ['mobilization.supervise'] },
  tracker: { operador: ['tracker.session'], supervisor: ['tracker.session', 'tracker.supervise'] },
};

export class FakeSteps {
  now = Date.parse('2026-10-04T12:00:00Z');
  offline = false;
  failNext: { status: number; error?: string } | null = null;
  requests: { method: string; path: string; body: Json; org: string | null }[] = [];
  /** Permite retener una petición en vuelo para probar carreras (cambio de empresa o de cuenta a mitad de un envío). */
  gate: ((path: string) => Promise<void>) | null = null;
  contract: Record<string, number> = { colaciones: 1, mobilization: 1, tracker: 1 };
  offlineHours = 72;
  private seq = 100;
  people: { id: number; name: string; email: string; password: string; verified: boolean; state: string }[] = [];
  sessions: Session[] = [];
  orgs = [{ uid: 'org-a', name: 'Empresa A', code: 'AAAA1111' }, { uid: 'org-b', name: 'Empresa B', code: 'BBBB2222' }];
  memberships: Membership[] = [];
  invitations: { token: string; email: string; orgUid: string; roles: [string, string][]; used?: boolean }[] = [];
  totems = [{ id: 1, orgUid: 'org-a', name: 'Casino 1', code: 'T1' }, { id: 2, orgUid: 'org-b', name: 'Casino B', code: 'TB' }];
  employees: Record<string, { name: string; orgUid: string; eligible: boolean }> = {
    BR0001: { name: 'Trabajador Uno', orgUid: 'org-a', eligible: true }, BR0002: { name: 'Trabajador Dos', orgUid: 'org-a', eligible: true },
    BR0003: { name: 'Sin Colación', orgUid: 'org-a', eligible: false }, BR9999: { name: 'Ajeno', orgUid: 'org-b', eligible: true },
  };
  registrations = new Map<string, { employee: string; orgUid: string; operator: number; day: string; code: string }>();
  trips: { id: number; orgUid: string; driver: number; state: string; name: string }[] = [];
  events = new Map<string, { tripId: number; passenger: string; type: string; by: number }>();

  // ---- utilidades de prueba ----
  addPerson(email: string, password = 'clave-segura-2026', name = email.split('@')[0]) {
    const p = { id: ++this.seq, name, email, password, verified: true, state: 'active' };
    this.people.push(p); return p;
  }
  grant(personId: number, orgUid: string, ...roles: [string, string][]) {
    let m = this.memberships.find((x) => x.personId === personId && x.orgUid === orgUid);
    if (!m) { m = { personId, orgUid, state: 'active', grants: [] }; this.memberships.push(m); }
    for (const [module, role] of roles) m.grants.push({ module, role });
    return m;
  }
  revokeGrants(personId: number, orgUid: string) { const m = this.memberships.find((x) => x.personId === personId && x.orgUid === orgUid)!; m.state = 'revoked'; m.endedAt = this.now; m.grants.forEach((g) => { g.revokedAt = this.now; }); }
  expireAccessTokens() { this.sessions.forEach((s) => { s.accessExp = this.now - 1; }); }
  revokeSessions(personId: number) { this.sessions.filter((s) => s.personId === personId).forEach((s) => { s.revoked = true; }); }
  addTrip(orgUid: string, driver: number, state = 'draft') { const t = { id: ++this.seq, orgUid, driver, state, name: `MV${this.seq}` }; this.trips.push(t); return t; }

  // ---- fetch ----
  fetch: typeof fetch = async (input, init) => {
    if (this.offline) throw new TypeError('network down');
    const url = new URL(String(input), 'https://fake.test');
    const path = url.pathname.replace(/^.*\/steps_app\/v1/, '');
    const body: Json = init?.body ? JSON.parse(String(init.body)) : {};
    const headers = new Headers(init?.headers as HeadersInit);
    this.requests.push({ method: init?.method ?? 'GET', path, body, org: headers.get('X-Steps-Org') });
    if (this.gate) await this.gate(path);
    if (this.failNext) { const f = this.failNext; this.failNext = null; return this.json({ ok: false, error: f.error ?? 'server_error', message: 'fallo', terminal: false }, f.status); }
    try { return this.json(this.route(init?.method ?? 'GET', path, body, headers, url)); }
    catch (e) { if (e instanceof HttpError) return this.json({ ok: false, error: e.code, message: e.code, terminal: e.status < 500 && e.status !== 401 && e.status !== 403 }, e.status); throw e; }
  };
  private json(payload: unknown, status = 200) { return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } }); }
  private fail(status: number, code: string): never { throw new HttpError(status, code); }
  private iso(t = this.now) { return new Date(t).toISOString().replace('.000Z', 'Z'); }

  private pair(personId: number, deviceUuid: string) {
    const s: Session = { personId, deviceUuid, access: `acc-${++this.seq}`, refresh: `ref-${++this.seq}`, accessExp: this.now + 30 * 60_000 };
    this.sessions.push(s); return this.tokens(s);
  }
  private tokens(s: Session) { return { access_token: s.access, refresh_token: s.refresh, access_expires_at: this.iso(s.accessExp), refresh_expires_at: this.iso(this.now + 30 * 86_400_000) }; }

  private auth(headers: Headers, needOrg: boolean, allowEnded = false) {
    const token = headers.get('Authorization')?.replace(/^Bearer /i, '');
    const s = this.sessions.find((x) => x.access === token);
    if (!token || !s) this.fail(401, 'session_invalid');
    if (s.revoked) this.fail(401, 'session_invalid');
    if (this.now >= s.accessExp) this.fail(401, 'token_expired');
    const person = this.people.find((p) => p.id === s.personId)!;
    if (person.state !== 'active') this.fail(401, 'session_revoked');
    let membership: Membership | undefined;
    if (needOrg) {
      const org = headers.get('X-Steps-Org');
      if (!org) this.fail(400, 'organization_required');
      membership = this.memberships.find((m) => m.personId === person.id && m.orgUid === org);
      if (!membership || !(membership.state === 'active' || (allowEnded && membership.endedAt))) this.fail(403, 'organization_not_authorized');
    }
    return { s, person, membership };
  }
  private active(g: Grant, at = this.now) { return !g.revokedAt || g.revokedAt > at; }
  private perms(m: Membership) { return new Set(m.state === 'active' ? m.grants.filter((g) => this.active(g)).flatMap((g) => PERMS[g.module]?.[g.role] ?? []) : []); }
  private require(m: Membership, p: string) { if (!this.perms(m).has(p)) this.fail(403, 'forbidden'); }
  private okAt(m: Membership, module: string, role: string, at: number, resource?: number): string | null {
    if (m.endedAt != null && at >= m.endedAt) return 'access_ended_before_capture';
    const valid = m.grants.filter((g) => g.module === module && g.role === role && this.active(g, at));
    if (!valid.length) return 'grant_not_valid_at_capture';
    if (resource != null && !valid.some((g) => !g.scope?.length || g.scope.includes(resource))) return 'resource_out_of_scope';
    return null;
  }

  private route(method: string, path: string, body: Json, headers: Headers, url: URL): Json {
    if (path === '/health') return { ok: true, api_version: 1, server_time: this.iso(), providers: { password: true, google: false, apple: false, test: false } };
    if (path === '/auth/register') {
      const email = String(body.email).toLowerCase();
      if (this.people.some((p) => p.email === email)) this.fail(409, 'email_in_use');
      if (String(body.password).length < 10) this.fail(422, 'weak_password');
      const p = this.addPerson(email, String(body.password), String(body.name)); p.verified = false;
      return { ok: true, ...this.pair(p.id, String((body.device as Json).uuid)) };
    }
    if (path === '/auth/login') {
      const p = this.people.find((x) => x.email === String(body.email).toLowerCase());
      if (!p || p.password !== body.password) this.fail(401, 'invalid_credentials');
      return { ok: true, ...this.pair(p.id, String((body.device as Json).uuid)) };
    }
    if (path === '/auth/refresh') {
      const s = this.sessions.find((x) => x.refresh === body.refresh_token || x.prevRefresh === body.refresh_token);
      if (!s || s.revoked) this.fail(401, 'session_invalid');
      if (s.prevRefresh === body.refresh_token) { s.revoked = true; this.fail(401, 'session_revoked'); }
      s.prevRefresh = s.refresh; s.refresh = `ref-${++this.seq}`; s.access = `acc-${++this.seq}`; s.accessExp = this.now + 30 * 60_000;
      return { ok: true, ...this.tokens(s) };
    }
    if (path === '/auth/logout') { const { s } = this.auth(headers, false); s.revoked = true; return { ok: true }; }
    if (path === '/me') {
      const { person } = this.auth(headers, false);
      const mine = this.memberships.filter((m) => m.personId === person.id).map((m) => ({ org_uid: m.orgUid, name: this.orgs.find((o) => o.uid === m.orgUid)!.name, state: m.state }));
      const onboarding = mine.some((m) => m.state === 'active') ? 'ready' : mine.some((m) => m.state === 'invited') ? 'invitation_pending' : mine.some((m) => m.state === 'requested') ? 'request_pending' : 'no_organization';
      return { ok: true, person: { id: person.id, name: person.name, email: person.email, state: person.state }, email_verified: person.verified, providers: ['password'], memberships: mine, onboarding, device: { id: 1 } };
    }
    if (path === '/invitations/accept') {
      const { person } = this.auth(headers, false);
      const inv = this.invitations.find((i) => i.token === body.token && !i.used);
      if (!inv) this.fail(400, 'invalid_invitation');
      if (inv.email !== person.email || !person.verified) this.fail(403, 'email_not_verified');
      inv.used = true; this.grant(person.id, inv.orgUid, ...inv.roles);
      return { ok: true, org_uid: inv.orgUid };
    }
    if (path === '/access/request') {
      const { person } = this.auth(headers, false);
      const org = this.orgs.find((o) => o.code === String(body.org_code).toUpperCase());
      if (!org) this.fail(404, 'invalid_org_code');
      if (!this.memberships.some((m) => m.personId === person.id && m.orgUid === org.uid)) this.memberships.push({ personId: person.id, orgUid: org.uid, state: 'requested', grants: [] });
      return { ok: true, state: 'requested' };
    }
    if (path === '/catalog') {
      const { s, membership } = this.auth(headers, true);
      const supported = Object.fromEntries(String(url.searchParams.get('supported') ?? '').split(',').filter(Boolean).map((x) => x.split(':')).map(([k, v]) => [k, Number(v)]));
      const modules: Json[] = [], incompatible: Json[] = [];
      for (const code of [...new Set(membership!.grants.filter((g) => this.active(g)).map((g) => g.module))]) {
        if (supported[code] !== this.contract[code]) { incompatible.push({ code, server_contract: this.contract[code], reason: 'app_update_required' }); continue; }
        const roles = [...new Set(membership!.grants.filter((g) => g.module === code && this.active(g)).map((g) => g.role))];
        modules.push({ code, name: code, icon: code, contract_version: this.contract[code], roles, permissions: [...new Set(roles.flatMap((r) => PERMS[code][r]))].sort() });
      }
      void s;
      return { ok: true, server_time: this.iso(), organization: { org_uid: membership!.orgUid, name: this.orgs.find((o) => o.uid === membership!.orgUid)!.name }, modules, incompatible_modules: incompatible, offline_until: this.iso(this.now + this.offlineHours * 3_600_000) };
    }
    if (path === '/devices') { this.auth(headers, false); return { ok: true, devices: [] }; }
    if (path === '/account/delete') { const { person } = this.auth(headers, false); person.state = 'deletion_requested'; return { ok: true }; }
    return this.domain(method, path, body, headers);
  }

  private domain(_method: string, path: string, body: Json, headers: Headers): Json {
    // ---- Colaciones ----
    if (path === '/colaciones/me') {
      const { membership } = this.auth(headers, true); this.require(membership!, 'colaciones.read_own');
      if (!membership!.employee) return { ok: true, linked: false };
      const mine = [...this.registrations.values()].filter((r) => r.orgUid === membership!.orgUid && r.employee === `E${membership!.employee}`);
      return { ok: true, linked: true, employee: `Trabajador ${membership!.employee}`, eligible: true, today: { registered: mine.length > 0, registration: mine[0]?.code ?? null, event_datetime: null }, recent: mine.map((r) => ({ registration: r.code, meal_date: r.day, product: 'Almuerzo' })) };
    }
    if (path === '/colaciones/totems') {
      const { membership } = this.auth(headers, true); this.require(membership!, 'colaciones.register');
      return { ok: true, max_batch_records: 100, totems: this.totems.filter((t) => t.orgUid === membership!.orgUid).map((t) => ({ ...t, product: 'Almuerzo', identification_method: 'barcode', allow_offline: true, offline_max_hours: 72 })) };
    }
    if (path === '/colaciones/register') {
      const { person, membership } = this.auth(headers, true, true);
      const totem = this.totems.find((t) => t.id === body.totem_id && t.orgUid === membership!.orgUid);
      if (!totem) this.fail(403, 'totem_not_authorized');
      const results = (body.records as Json[]).map((r) => {
        const at = r.offline === false ? this.now : Date.parse(String(r.event_datetime));
        const why = this.okAt(membership!, 'colaciones', 'operador', at, totem.id);
        if (why) return { client_uuid: r.client_uuid, status: 'rejected', message: why, terminal: true };
        if (this.registrations.has(String(r.client_uuid))) return { client_uuid: r.client_uuid, status: 'duplicate', terminal: true };
        const emp = this.employees[String(r.identifier)];
        if (!emp || emp.orgUid !== membership!.orgUid) return { client_uuid: r.client_uuid, status: 'rejected', message: 'No se encontró un trabajador activo con esa identificación.', terminal: true };
        if (!emp.eligible) return { client_uuid: r.client_uuid, status: 'rejected', message: 'El trabajador no está habilitado para recibir colación.', terminal: true };
        const day = this.iso(at).slice(0, 10);
        if ([...this.registrations.values()].some((x) => x.employee === emp.name && x.day === day)) return { client_uuid: r.client_uuid, status: 'duplicate', terminal: true };
        const code = `COL/${this.registrations.size + 1}`;
        this.registrations.set(String(r.client_uuid), { employee: emp.name, orgUid: membership!.orgUid, operator: person.id, day, code });
        return { client_uuid: r.client_uuid, status: 'registered', registration: code, employee: emp.name, terminal: true };
      });
      return { ok: true, results };
    }
    // ---- Movilización ----
    const tripMatch = path.match(/^\/mobilization\/trips\/(\d+)(\/\w+)?$/);
    if (path === '/mobilization/trips') {
      const { person, membership } = this.auth(headers, true); this.require(membership!, 'mobilization.drive');
      return { ok: true, server_time: this.iso(), trips: this.trips.filter((t) => t.driver === person.id && t.orgUid === membership!.orgUid && ['draft', 'open'].includes(t.state)).map((t) => this.tripOut(t)) };
    }
    if (tripMatch) {
      const { person, membership } = this.auth(headers, true, tripMatch[2] === '/events');
      const trip = this.trips.find((t) => t.id === Number(tripMatch[1]) && t.driver === person.id && t.orgUid === membership!.orgUid);
      if (!trip) this.fail(404, 'trip_not_found');
      if (tripMatch[2] === '/open') { this.require(membership!, 'mobilization.drive'); if (trip.state === 'draft') trip.state = 'open'; return { ok: true, trip: this.tripOut(trip) }; }
      if (tripMatch[2] === '/close') { this.require(membership!, 'mobilization.drive'); if (trip.state === 'open') trip.state = 'closed'; return { ok: true, trip: this.tripOut(trip) }; }
      if (tripMatch[2] === '/events') {
        const results = (body.events as Json[]).map((e) => {
          const key = `${trip.id}:${e.idempotency_key}`;
          if (this.events.has(key)) return { idempotency_key: e.idempotency_key, status: 'duplicate', terminal: true };
          const why = this.okAt(membership!, 'mobilization', 'conductor', Date.parse(String(e.device_datetime)));
          if (why) return { idempotency_key: e.idempotency_key, status: 'rejected', message: why, terminal: true };
          if (trip.state !== 'open') return { idempotency_key: e.idempotency_key, status: 'rejected', message: 'trip_not_open', terminal: true };
          const emp = this.employees[String(e.identifier)];
          if (!emp || emp.orgUid !== membership!.orgUid) return { idempotency_key: e.idempotency_key, status: 'rejected', message: 'passenger_not_authorized', terminal: true };
          this.events.set(key, { tripId: trip.id, passenger: emp.name, type: String(e.event_type), by: person.id });
          return { idempotency_key: e.idempotency_key, status: 'created', terminal: true };
        });
        return { ok: true, results, trip: this.tripOut(trip) };
      }
      this.require(membership!, 'mobilization.drive');
      return { ok: true, trip: this.tripOut(trip, true) };
    }
    if (path === '/mobilization/supervisor/trips') {
      const { membership } = this.auth(headers, true); this.require(membership!, 'mobilization.supervise');
      return { ok: true, date: '2026-10-04', trips: this.trips.filter((t) => t.orgUid === membership!.orgUid).map((t) => ({ ...this.tripOut(t, true), driver: this.people.find((p) => p.id === t.driver)?.name })) };
    }
    this.fail(404, 'not_found');
  }
  private tripOut(t: { id: number; state: string; name: string }, withEvents = false): Json {
    const evs = [...this.events.entries()].filter(([, e]) => e.tripId === t.id);
    const boarded = evs.filter(([, e]) => e.type === 'boarding').length, alighted = evs.filter(([, e]) => e.type === 'alighting').length;
    const out: Json = { id: t.id, uuid: `uuid-${t.id}`, name: t.name, state: t.state, date: '2026-10-04', scheduled_time: null, route: 'Ruta prueba', direction: 'ida', vehicle: 'Bus 1', capacity: 2, aboard_count: boarded - alighted, boarded_count: boarded, alighted_count: alighted, overcapacity: boarded - alighted > 2 };
    if (withEvents) out.events = evs.map(([k, e]) => ({ idempotency_key: k, passenger: e.passenger, event_type: e.type, device_datetime: this.iso(), state: 'valid', by: this.people.find((p) => p.id === e.by)?.name ?? null }));
    return out;
  }
}

class HttpError extends Error { constructor(readonly status: number, readonly code: string) { super(code); } }
