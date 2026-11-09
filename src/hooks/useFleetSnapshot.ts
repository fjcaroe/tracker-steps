import { useCallback, useEffect, useMemo, useState } from 'react';
import { allPages, type FleetAsset, type FleetContext } from '../services/fleetApi';
import { readFleetDrivers } from '../services/odooOperations';

export function useFleetSnapshot(context: FleetContext | null, demo: boolean) {
  const [assets, setAssets] = useState<FleetAsset[]>([]);
  const [drivers, setDrivers] = useState(() => new Map<string, string | null>());
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision(r => r + 1), []);
  useEffect(() => {
    if (!context || demo) return;
    let active = true;
    let pending = false;
    const load = async () => {
      if (pending) return;
      pending = true;
      try {
        const items = await allPages<FleetAsset>('fleet/snapshot', context);
        if (!active) return;
        setAssets(items);
        setError('');
        setLoading(false);
        const names = await readFleetDrivers(context, items.map(item => item.asset_id))
          .catch(() => new Map<string, string | null>());
        if (active) setDrivers(names);
      } catch (e) {
        if (active) {
          setError((e as Error).message);
          setAssets([]);
          setDrivers(new Map());
        }
      } finally {
        pending = false;
        if (active) setLoading(false);
      }
    };
    void load();
    const timer = window.setInterval(() => void load(), 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, [context, demo, revision]);
  const identifiedAssets = useMemo(() => assets.map(asset => ({
    ...asset, driver_name: drivers.get(asset.asset_id),
  })), [assets, drivers]);
  return { assets: identifiedAssets, error, loading: !demo && loading, refresh };
}
