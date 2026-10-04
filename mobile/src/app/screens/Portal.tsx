import { useRuntime, useSession, useSyncState } from '../context';
import { visibleModules, type ModuleManifest } from '../../modules/registry';
import { Banner, Button, Card, Chip, Empty } from '../../shared/ui';

export function SyncChip() {
  const s = useSyncState();
  if (s.authRequired) return <Chip tone="bad">Requiere acceso</Chip>;
  if (s.rejected) return <Chip tone="bad">{s.rejected} con problema</Chip>;
  if (s.syncing) return <Chip tone="warn">Enviando…</Chip>;
  if (s.pending) return <Chip tone="warn">{s.pending} por enviar</Chip>;
  return <Chip tone="ok">Todo enviado</Chip>;
}

/** Portada: módulos y acciones habilitados para esta persona y empresa, con contexto de empresa y sincronización visibles. */
export default function Portal({ manifests, onOpen }: { manifests: ModuleManifest[]; onOpen: (id: string, view?: string) => void }) {
  const { session } = useRuntime();
  const { catalog, access, notice } = useSession();
  const modules = visibleModules(manifests, catalog);
  const incompatible = catalog?.incompatible_modules ?? [];

  return (
    <div className="ui-screen">
      <Card label="Empresa activa">
        <div className="ui-row"><div><small>Empresa</small><h2>{catalog?.organization.name ?? '…'}</h2></div><SyncChip /></div>
      </Card>
      {notice && <Banner tone="warn">{notice}</Banner>}
      {access === 'offline_valid' && <Banner tone="warn">Sin conexión: puedes seguir trabajando hasta {catalog ? new Date(catalog.offline_until).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' }) : '—'}. Tus datos se enviarán al volver la señal.</Banner>}
      {access === 'offline_expired' && <Banner tone="bad">Pasó el plazo sin conexión. Conéctate para validar tu acceso y seguir registrando; lo que ya guardaste no se pierde.</Banner>}
      {incompatible.length > 0 && <Banner tone="warn">Hay módulos habilitados para ti que requieren actualizar la app: {incompatible.map((m) => m.code).join(', ')}.</Banner>}

      {modules.some((m) => m.manifest.quickActions?.some((a) => session.can(a.permission))) && (
        <Card label="Acciones frecuentes">
          <h3>Acciones frecuentes</h3>
          <div className="ui-grid">
            {modules.flatMap((m) => (m.manifest.quickActions ?? []).filter((a) => session.can(a.permission)).map((a) => (
              <Button key={`${m.manifest.id}:${a.id}`} variant="primary" onClick={() => onOpen(m.manifest.id, a.id)}>{a.label}</Button>
            )))}
          </div>
        </Card>
      )}

      {modules.length === 0
        ? <Card><Empty title="Aún no tienes módulos habilitados" hint="Tu administrador puede asignarte accesos desde Odoo. Vuelve a revisar más tarde." /><Button onClick={() => void session.revalidate()}>Revisar de nuevo</Button></Card>
        : <div className="ui-grid">{modules.map(({ manifest }) => (
            <Button key={manifest.id} className="ui-card--tap" onClick={() => onOpen(manifest.id)} aria-label={`Abrir ${manifest.name}`}>
              <strong>{manifest.name}</strong><br /><small>{manifest.tagline}</small>
            </Button>))}</div>}
    </div>
  );
}
