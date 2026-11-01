import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('transfer_scope',Path(__file__).resolve().parents[2]/'gps/transfer_scope.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class ScopeTests(unittest.TestCase):
 def test_contacts_and_append_only_history(self):
  before={'gps_device_registrations':[{'id':'r','phone':'test','version':2,'receiver_mode':'forward','receiver_seen_at':'old'}],'gps_positions':[{'id':'p','lat':1}]}
  after={'gps_device_registrations':[{'id':'r','phone':'test','version':2,'receiver_mode':'forward','receiver_seen_at':'new'}],'gps_positions':[{'id':'new','lat':2},{'id':'p','lat':1}]}
  module.validate_snapshot(before,after)
 def test_history_must_not_disappear_or_change(self):
  for new in ([],[{'id':'p','lat':2}]):
   with self.assertRaises(ValueError):module.validate_snapshot({'gps_positions':[{'id':'p','lat':1}]},{'gps_positions':new})
 def test_mode_assignment_and_version_are_still_guarded(self):
  for key,value in [('version',3),('receiver_mode','capture'),('phone','different')]:
   old={'id':'r','version':2,'receiver_mode':'forward','phone':'test'}
   with self.assertRaises(ValueError):module.validate_snapshot({'gps_device_registrations':[old]},{'gps_device_registrations':[{**old,key:value}]})
  with self.assertRaises(ValueError):module.validate_snapshot({'gps_assignments':[{'id':'a','device_id':'one'}]},{'gps_assignments':[{'id':'a','device_id':'two'}]})
if __name__=='__main__':unittest.main()
