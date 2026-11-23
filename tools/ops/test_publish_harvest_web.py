"""Routing publication must never modify neighboring applications or hosts."""
from pathlib import Path
import unittest
from publish_harvest_web import patch_config


class RoutingCase(unittest.TestCase):
    def test_only_exact_tls_host_and_harvest_locations_change(self):
        neighbor = 'server { listen 443 ssl; server_name stepsapp.cl; location / { proxy_pass http://127.0.0.1:8069; } }'
        http = 'server { listen 80; server_name desarrollo.stepsapp.cl; return 301 https://$host$request_uri; }'
        source = neighbor+'\n'+http+'''\nserver {
 listen 443 ssl;
 server_name desarrollo.stepsapp.cl;
 location = /cosecha { return 301 /cosecha/; }
 location ^~ /cosecha/ { alias /var/www/cosecha/; try_files $uri $uri/ /cosecha/index.html; }
 location /web { proxy_pass http://127.0.0.1:8075; }
 # an unrelated comment with a } brace
}'''
        result = patch_config(source, 'desarrollo.stepsapp.cl', Path('/var/www/steps-harvest-releases/development/test/app'))
        self.assertIn(neighbor, result)
        self.assertIn(http, result)
        self.assertIn('location /web { proxy_pass http://127.0.0.1:8075; }', result)
        self.assertNotIn('alias /var/www/cosecha/', result)
        self.assertEqual(result.count('location = /cosecha/sw.js'), 1)
        self.assertEqual(result.count('no-cache'), 3)
        again = patch_config(result, 'desarrollo.stepsapp.cl', Path('/var/www/steps-harvest-releases/development/next/app'))
        self.assertNotIn('/development/test/app', again)
        self.assertIn(neighbor, again)
        with self.assertRaises(AssertionError):
            patch_config(source, 'cerroelplomo.stepsapp.cl', Path('/tmp/unused'))


if __name__ == '__main__':
    unittest.main()
