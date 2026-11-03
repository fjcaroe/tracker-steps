"""Keep independent mobile/API routes intact across repeated portal releases."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('deploy',Path(__file__).resolve().parents[2]/'ops/deploy_gps_commissioning.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class Routing(unittest.TestCase):
 def test_private_mobile_and_development_api_are_preserved(self):
  original='location = /truck { return 301 /truck/; }\nlocation ^~ /truck/assets/ { alias /private/mobile/assets/; }\nlocation ^~ /tracker-dev-api/ { proxy_pass http://127.0.0.1:8012/; }\n'
  first=module.tracker_entry_locations(original,Path('/release/a'),'dev')
  self.assertTrue(first.startswith(original));self.assertIn('alias /release/a/index.html;',first)
  second=module.tracker_entry_locations(first,Path('/release/b'),'dev')
  self.assertTrue(second.startswith(original));self.assertNotIn('/release/a',second);self.assertEqual(second.count('location = /tracker {'),1)
 def test_cerro_legacy_entry_redirects_without_replacing_assets(self):
  result=module.tracker_entry_locations('location = /truck { return 301 /truck/; }\nlocation ^~ /truck/assets/ { alias /mobile/assets/; }\n',Path('/release/a'),'cerro')
  self.assertIn('location = /truck { return 302 /tracker$is_args$args; }',result)
  self.assertIn('location = /truck/ { return 302 /tracker$is_args$args; }',result)
  self.assertIn('alias /mobile/assets/;',result)
 def test_unknown_entry_is_rejected(self):
  with self.assertRaises(AssertionError):module.tracker_entry_locations('location /tracker { proxy_pass http://other; }',Path('/release/a'),'cerro')
 def test_unified_entry_reaches_jornada_in_both_environments(self):
  original='location = /truck { return 301 /truck/; }\nlocation ^~ /truck/assets/ { alias /mobile/assets/; }\n'
  for scope in ('dev','cerro'):
   previous=module.tracker_entry_locations(original,Path('/release/a'),scope)
   result=module.tracker_entry_locations(previous,Path('/release/b'),scope,Path('/entry/b'))
   self.assertEqual(result.count('return 302 /tracker/jornada/$is_args$args;'),3)
   self.assertIn('alias /entry/b/jornada.html;',result)
   self.assertIn('alias /entry/b/gps.html;',result)
   self.assertIn('alias /mobile/assets/;',result)
   self.assertIn('/truck/$1 last;',result)
   self.assertEqual(module.tracker_entry_locations(result,Path('/release/b'),scope,Path('/entry/b')).strip(),result.strip())
 def test_shell_keeps_relative_mobile_assets_and_links_back(self):
  result=module.tracker_shell('<head><title>Steps Móvil</title><script src="./assets/index.js"></script></head><body><div id="root"></div></body>','jornada')
  self.assertNotIn('src="./assets/index.js"',result)
  self.assertIn('await import("./assets/index.js")',result)
  self.assertIn('context.vehicle_limited',result)
  self.assertIn('<a href="/tracker">GPS y recorridos</a>',result)
  self.assertIn('<a href="/tracker/jornada/" aria-current="page">Jornada y terreno</a>',result)

if __name__=='__main__':unittest.main()
