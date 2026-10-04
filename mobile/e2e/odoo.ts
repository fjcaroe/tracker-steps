// Utilidades del recorrido E2E: lectura del resumen de datos de demostración y acceso al backend de Odoo como un USUARIO REAL (con sus permisos).
import { readFileSync } from 'node:fs';

export type Summary = {
  password: string;
  companies: Record<'norte' | 'sur', { org_uid: string; org_code: string; totem_ids: number[]; employee_barcodes: Record<string, string>; vehicle_id: number; route_id: number }>;
  users: Record<string, string>;
  trips: { conductor1: number; conductor2: number; multi_sur: number };
  invitation: { email: string; code: string };
};

export const BASE = process.env.STEPS_E2E_BASE ?? 'http://localhost:8070';
export const DB = process.env.STEPS_E2E_DB ?? 'demo';
export const summary = (): Summary => JSON.parse(readFileSync(process.env.STEPS_DEMO_SUMMARY ?? '/opt/odoo-env/demo-summary.json', 'utf8'));

export class OdooUser {
  private cookie = '';
  private constructor(readonly login: string) {}

  static async login(login: string, password: string): Promise<OdooUser> {
    const u = new OdooUser(login);
    const r = await fetch(`${BASE}/web/session/authenticate`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: { db: DB, login, password } }) });
    const body = await r.json();
    if (!body.result?.uid) throw new Error(`No se pudo autenticar a ${login} en Odoo: ${JSON.stringify(body.error ?? body.result)}`);
    u.cookie = (r.headers.getSetCookie?.() ?? []).map((c) => c.split(';')[0]).join('; ');
    return u;
  }

  /** Llama a un método del ORM con los permisos reales del usuario. Devuelve {result} o {error: mensaje}. */
  async call<T = unknown>(model: string, method: string, args: unknown[] = [], kwargs: Record<string, unknown> = {}): Promise<{ result?: T; error?: string }> {
    const r = await fetch(`${BASE}/web/dataset/call_kw/${model}/${method}`, { method: 'POST', headers: { 'Content-Type': 'application/json', Cookie: this.cookie },
      body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: { model, method, args, kwargs } }) });
    const body = await r.json();
    return body.error ? { error: body.error.data?.name ?? body.error.message } : { result: body.result as T };
  }
  async ok<T = unknown>(model: string, method: string, args: unknown[] = [], kwargs: Record<string, unknown> = {}): Promise<T> {
    const r = await this.call<T>(model, method, args, kwargs);
    if (r.error) throw new Error(`${this.login} → ${model}.${method}: ${r.error}`);
    return r.result as T;
  }
  searchRead<T = Record<string, unknown>>(model: string, domain: unknown[], fields: string[]): Promise<T[]> {
    return this.ok<T[]>(model, 'search_read', [domain], { fields });
  }
}
