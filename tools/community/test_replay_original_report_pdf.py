import unittest

from replay_original_report_pdf import rewrite_base, variant_arguments


class StaticReplayBoundaryCase(unittest.TestCase):
    def test_argument_contrast_preserves_every_other_original_option(self):
        original = ['--disable-local-file-access', '--header-spacing', '52', '--dpi', '90',
                    '--javascript-delay', '1000']
        changed = variant_arguments(original, 5, 3000)
        self.assertEqual(changed, ['--disable-local-file-access', '--header-spacing', '5', '--dpi', '90',
                                   '--javascript-delay', '3000'])
        self.assertEqual(original[2], '52')
        with self.assertRaises(ValueError):
            variant_arguments(original + ['--cookie-jar', '/private/cookie'])

    def test_only_one_loopback_origin_can_be_substituted(self):
        raw = b'<html><base href="http://127.0.0.1:1234"/><p>Original stored bytes</p></html>'
        changed, original = rewrite_base(raw, 'http://127.0.0.1:4321')
        self.assertEqual(original, 'http://127.0.0.1:1234')
        self.assertEqual(changed, raw.replace(b':1234', b':4321'))
        for bad in (b'<base href="https://external.example"/>', raw + raw):
            with self.assertRaises(ValueError):
                rewrite_base(bad, 'http://127.0.0.1:4321')


if __name__ == '__main__':
    unittest.main()
