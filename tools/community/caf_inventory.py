"""Private read-only native CAF metadata inventory; never reads binary keys/XML.

Run on the documented host as a PostgreSQL peer with SELECT permissions:
sudo -u postgres python3.10 caf_inventory.py --database CERRO_EL_PLOMO
  --output /private/artifact/caf-inventory.json
No addon/Enterprise source or CAF/certificate payload is read or copied.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess


QUERIES = {
    'licenses': """SELECT name,license,state FROM ir_module_module WHERE name IN
        ('l10n_cl','l10n_cl_edi','l10n_cl_edi_stock','l10n_cl_edi_exports',
         'certificate','account_edi') ORDER BY name""",
    'models': """SELECT id,model,state FROM ir_model WHERE model IN
        ('l10n_cl.dte.caf','certificate.certificate','certificate.key') ORDER BY model""",
    'fields': """SELECT id,model,name,ttype,relation,required,readonly,store FROM ir_model_fields
        WHERE model IN ('l10n_cl.dte.caf','certificate.certificate','certificate.key')
        OR (model IN ('account.move','res.company','l10n_latam.document.type') AND
        (name ILIKE '%caf%' OR name ILIKE '%l10n_cl%' OR name ILIKE '%certificate%'))
        ORDER BY model,name""",
    'acl': """SELECT a.id,a.name,m.model,a.group_id,a.perm_read,a.perm_write,
        a.perm_create,a.perm_unlink FROM ir_model_access a
        JOIN ir_model m ON m.id=a.model_id WHERE m.model IN
        ('l10n_cl.dte.caf','certificate.certificate','certificate.key') ORDER BY a.id""",
    'rules': """SELECT r.id,r.name,m.model,r.perm_read,r.perm_write,r.perm_create,
        r.perm_unlink,r.active FROM ir_rule r JOIN ir_model m ON m.id=r.model_id
        WHERE m.model IN ('l10n_cl.dte.caf','certificate.certificate','certificate.key') ORDER BY r.id""",
    'xmlids': """SELECT module,name,model,res_id,noupdate FROM ir_model_data WHERE
        module IN ('l10n_cl_edi','l10n_cl_edi_stock','l10n_cl_edi_exports','certificate')
        AND (name ILIKE '%caf%' OR model IN ('ir.model.access','ir.rule')) ORDER BY module,name""",
    'views': """SELECT id,name,model,inherit_id,active FROM ir_ui_view WHERE model IN
        ('l10n_cl.dte.caf','certificate.certificate','certificate.key') ORDER BY id""",
    'foreign_keys': """SELECT conname,pg_get_constraintdef(oid) AS definition FROM pg_constraint
        WHERE contype='f' AND (conrelid='l10n_cl_dte_caf'::regclass
        OR confrelid='l10n_cl_dte_caf'::regclass) ORDER BY conname""",
    'caf_count_only': 'SELECT count(*) AS records FROM l10n_cl_dte_caf',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_]+', args.database):
        parser.error('Invalid database identifier')
    output = args.output.resolve()
    source = Path(__file__).resolve().parents[2]
    if source in output.parents or not args.output.is_absolute():
        parser.error('Evidence must use an absolute path outside the source checkout')
    # Every query is executed inside one read-only repeatable-read transaction.
    # There is intentionally no query for CAF XML, RSASK or certificates.
    statements = ['BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;']
    for name, query in QUERIES.items():
        statements.append("SELECT jsonb_build_object('section','" + name
                          + "','rows',coalesce(jsonb_agg(t),'[]'::jsonb)) FROM (" + query + ') t;')
    statements.append('ROLLBACK;')
    result = subprocess.run(['psql','-XAtq','-v','ON_ERROR_STOP=1','-d',args.database],
                            input='\n'.join(statements), text=True,
                            capture_output=True, check=True)
    report = {'scope': 'native-metadata-only-no-CAF-payload',
              'database': args.database,
              'sections': [json.loads(line) for line in result.stdout.splitlines() if line]}
    output.parent.mkdir(parents=True, exist_ok=True)
    # Private artifact, no public repo data or secrets in terminal output.
    with output.open('x', encoding='utf-8') as stream:
        output.chmod(0o600)
        json.dump(report, stream, indent=2)
    print(json.dumps({'evidence': str(output), 'sections': len(report['sections'])}))


if __name__ == '__main__':
    main()
