import { useRuntime, useSession } from '../context';
import { Button, Card, Icon } from '../../shared/ui';

/** Elección de empresa cuando la persona tiene más de una membresía activa. Cada empresa tiene su propia cola y su propio catálogo. */
export default function CompanyPicker() {
  const { session } = useRuntime();
  const { me } = useSession();
  const active = me?.memberships.filter((m) => m.state === 'active') ?? [];
  return (
    <div className="ui-screen">
      <Card label="Elegir empresa"><span className="ui-eyebrow">Tu espacio de trabajo</span>
        <h2>¿Con qué empresa trabajas ahora?</h2>
        <p className="muted">Puedes cambiar de empresa cuando quieras desde tu perfil. Lo pendiente de cada empresa se guarda por separado.</p>
      </Card>
      {active.map((m) => <Button key={m.org_uid} className="ui-card--tap ui-module" onClick={() => void session.selectOrg(m.org_uid)}><span className="ui-module__icon"><Icon name="company" /></span><strong className="ui-module__text">{m.name}</strong><Icon name="arrow" /></Button>)}
    </div>
  );
}
