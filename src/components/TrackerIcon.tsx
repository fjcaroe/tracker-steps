export default function TrackerIcon({ name, size = 22 }: { name: string; size?: number }) {
  const paths: Record<string, string> = {
    zones: 'm4 7 11-4 6 12-11 6-7-6Z M4 7h.01M15 3h.01M21 15h.01M10 21h.01', settings: 'M4 7h16M4 17h16M8 4v6m8 4v6', home: 'M3 10 12 3l9 7v11h-6v-7H9v7H3Z', live: 'm3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2Zm6-2v16m6-14v16',
    fleet: 'm5 6 2-3h10l2 3 2 5v8h-3v-3H6v3H3v-8Zm-1 5h16M7 13h1m8 0h1',
    protection: 'M12 3 3 6v6c0 5 9 9 9 9s9-4 9-9V6Zm-5 9 3 3 7-7',
    ops: 'M4 19V9m6 10V5m6 14v-7M2 19h20', plus: 'M12 5v14M5 12h14', arrow: 'M5 12h14m-6-6 6 6-6 6',
    signal: 'M3 18v3m6-8v8m6-13v13m6-18v18', history: 'M3 11a9 9 0 1 1 2 7M3 4v7h7m2-4v6l4 2',
    truck: 'M2 5h12v12H2Zm12 5h4l4 4v3h-8M5 17v3m13-3v3',
    tractor: 'M5 4h8v9h4l1-5h3v10h-3m-8 0h3M2 12h7v6H2Zm3 5v4m12-6v6',
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.fleet}/></svg>;
}
