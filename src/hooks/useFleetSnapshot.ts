import { useCallback, useEffect, useState } from 'react';
import { allPages, type FleetAsset, type FleetContext } from '../services/fleetApi';

export function useFleetSnapshot(context: FleetContext | null, demo: boolean) {
  const [assets, setAssets] = useState<FleetAsset[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision(r => r + 1), []);
  useEffect(() => {
    if (!context || demo) return;
    let active = true;
    const load = async () => {
      try {
        const items = await allPages<FleetAsset>('fleet/snapshot', context);
        if (active) { setAssets(items); setError(''); }
      } catch (e) { if (active) { setError((e as Error).message); setAssets([]); } }
      finally { if (active) setLoading(false); }
    };
    void load();
    const timer = window.setInterval(() => void load(), 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, [context, demo, revision]);
  return { assets, error, loading: !demo && loading, refresh };
}
