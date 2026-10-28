"""Derive a private Simple Digital book package, changing only its real prerequisite."""
import argparse
import ast
import hashlib
import json
from pathlib import Path


def hashes(addon):
    return {str(p.relative_to(addon)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(addon.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addon',type=Path,required=True)
    args=parser.parse_args();addon=args.addon.resolve()
    assert addon.is_relative_to(Path('/opt/steps-validation'))
    assert addon.name=='step_hr_remuneration_book' and addon.parent.name=='addons'
    target=addon/'__manifest__.py';original=target.read_bytes()
    manifest=ast.literal_eval(original.decode('utf-8-sig'))
    assert manifest['license']=='LGPL-3' and 'hr_payroll' in manifest['depends']
    assert original.count(b'"hr_payroll"')==1
    before=hashes(addon)
    target.write_bytes(original.replace(b'"hr_payroll"',b'"step_simpledigital_oca_security"'))
    after=hashes(addon)
    assert [name for name in before if before[name]!=after[name]]==['__manifest__.py']
    result={'license':'LGPL-3','source_files':before,'candidate_files':after,
            'transformation':'real_simpledigital_prerequisite_only',
            'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'generic_canonical_dependency_retired':False,'full_cerro_conversion':False}
    (addon.parent.parent/'book-derivation.json').write_text(json.dumps(result,indent=2))
    print('REAL_BOOK_CANDIDATE_BUILT',len(after))


if __name__=='__main__':main()
