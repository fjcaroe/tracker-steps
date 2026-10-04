import { Component, Suspense, lazy, useMemo, type ReactNode } from 'react';
import { useRuntime } from '../context';
import type { ModuleManifest } from '../../modules/registry';
import { Banner, Button, Spinner } from '../../shared/ui';

class Boundary extends Component<{ onExit: () => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed
      ? <div className="ui-screen"><Banner tone="bad">Este módulo tuvo un problema y se cerró. Tus datos pendientes siguen guardados.</Banner><Button onClick={this.props.onExit}>Volver al inicio</Button></div>
      : this.props.children;
  }
}

/** Carga el módulo bajo demanda. Un fallo del módulo no tumba la sesión ni la cola. */
export default function ModuleHost({ manifest, view, onExit }: { manifest: ModuleManifest; view?: string; onExit: () => void }) {
  const runtime = useRuntime();
  const Module = useMemo(() => lazy(manifest.load), [manifest]);
  return <Boundary onExit={onExit}><Suspense fallback={<Spinner />}><Module runtime={runtime} onExit={onExit} view={view} /></Suspense></Boundary>;
}
