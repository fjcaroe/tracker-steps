"""Allow live observations to advance; never accept loss or ownership/config drift."""
DIAGNOSTIC={'receiver_seen_at','receiver_fix_at','receiver_fix_received_at','receiver_lat','receiver_lon','receiver_speed','receiver_error','receiver_pending'}
def validate_snapshot(before,after):
 if set(before)!=set(after):raise ValueError('Migration table scope changed')
 for table,old in before.items():
  new=after[table]
  def keyed(rows):return {str(r.get('id',r.get('asset_id'))):{k:v for k,v in r.items() if not(table=='gps_device_registrations' and k in DIAGNOSTIC)} for r in rows}
  a,b=keyed(old),keyed(new)
  if table in ('gps_positions','gps_audit_events'):
   if any(key not in b or value!=b[key] for key,value in a.items()):raise ValueError('Existing history changed: '+table)
  elif a!=b:raise ValueError('Personal identity, assignment or policy changed: '+table)
