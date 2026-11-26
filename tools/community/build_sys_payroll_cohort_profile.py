"""Build the exact early free providers and private manifests for an admitted SyS cohort."""
import argparse
import ast
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from build_numeric_input_engine import hashes, require, seal
from derive_sys_history_fields import build as build_history
from derive_sys_structure_accounting import build as build_structure
from original_history_engine_contract import _snapshot


# Free engine bytes previously derived and tested from the reviewed OCA pin.
# Only the two free modules are taken from this input, never a database or seed.
SOURCE = {
    "payroll": "98e0de4ae2b921e993c067f3ba3e280d46bfca8b2f2db5f5dbee05891b60b2a5",
    "payroll_account": "b5b440ba8dc52732ea133f47ae13f9bba3aa3c6e66955898aeb240e9b3d0d933",
}


REQUIRED_MODELS = b"""from odoo import fields, models


class Structure(models.Model):
    _inherit = 'hr.payroll.structure'

    type_id = fields.Many2one(required=True)


class Rule(models.Model):
    _inherit = 'hr.salary.rule'

    code = fields.Char(required=True)
    category_id = fields.Many2one(required=True, ondelete='restrict')


class RuleCategory(models.Model):
    _inherit = 'hr.salary.rule.category'

    code = fields.Char(required=True)


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    name = fields.Char(required=True)


class PayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    # The line follows the rule classification without a stored column.
    category_id = fields.Many2one(related='salary_rule_id.category_id', store=False,
                                 readonly=True, copy=False, required=False)
"""


def build(source, repository, output):
    source = source.resolve(strict=True)
    repository = repository.resolve(strict=True)
    output = output.resolve()
    require(output.is_relative_to(Path('/opt/steps-validation')) and not output.exists()
            and not output.is_relative_to(source) and not output.is_relative_to(repository),
            "Unoccupied private SyS profile required")
    for name, reviewed in SOURCE.items():
        folder = source / name
        require(not folder.is_symlink() and not (folder / "__manifest__.py").is_symlink() and
                ast.literal_eval((folder / "__manifest__.py").read_text())["license"] == "LGPL-3",
                "Free source manifest required")
        require(seal(hashes(_snapshot(folder))) == reviewed, "SyS input engine bytes changed")
    with TemporaryDirectory(dir=output.parent) as scratch:
        top = Path(scratch) / 'profile'
        top.mkdir()
        input_type = (repository / 'step_payroll_oca_api/models/input_type.py').read_bytes()
        history = build_history(source, top / 'history-engine', input_type)
        engine = build_structure(top / 'history-engine', top / 'engine')
        own = {}
        for module in ('step_payroll_oca_api', 'step_simpledigital_oca_security'):
            files = _snapshot(repository / module)
            manifest = ast.literal_eval(files['__manifest__.py'].decode())
            require(manifest['license'] == 'LGPL-3', 'SyS requires free compatibility providers')
            # The original security policies already belong to the original roles.
            # Installing the OCA policy seeds would add memberships or new rights.
            kept = [name for name in manifest['data'] if name != 'security.xml' and not name.startswith('security/')]
            require(len(kept) < len(manifest['data']), 'SyS policy seed manifest drift')
            manifest['data'] = kept
            old = seal(hashes(files))
            files['__manifest__.py'] = (repr(manifest) + '\n').encode()
            if module == 'step_payroll_oca_api':
                require('models/step_sys_required.py' not in files, 'SyS required overlay already present')
                files['models/step_sys_required.py'] = REQUIRED_MODELS
                files['models/__init__.py'] += b'\nfrom . import step_sys_required\n'
            target = top / 'own-profile' / module
            for name, body in files.items():
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
            require(_snapshot(target) == files, 'SyS private addon verification failed')
            own[module] = {'original': old, 'derived': seal(hashes(files))}
        result = {'source': SOURCE, 'history': history, 'engine': engine, 'own': own}
        (top / 'profile.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
        top.rename(output)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.repository, args.output), sort_keys=True))
