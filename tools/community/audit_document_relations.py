"""Compare the native Documents relationships in private restores without opening files or links."""
import argparse
import json
import re
import subprocess


SQL = """
SELECT json_build_object(
    'documents', count(*),
    'types', (SELECT json_object_agg(kind, n) FROM
        (SELECT COALESCE(type, '(empty)') kind, count(*) n FROM documents_document GROUP BY type) t),
    'with_attachment', count(d.attachment_id),
    'unique_attachments', count(DISTINCT d.attachment_id),
    'missing_attachments', count(*) FILTER (WHERE d.attachment_id IS NOT NULL AND a.id IS NULL),
    'attachments_in_filestore', count(*) FILTER (WHERE a.store_fname IS NOT NULL),
    'with_folder', count(d.folder_id),
    'missing_folders', count(*) FILTER (WHERE d.folder_id IS NOT NULL AND parent.id IS NULL),
    'folder_target_not_folder', count(*) FILTER (WHERE parent.id IS NOT NULL AND parent.type <> 'folder'),
    'shortcuts', count(d.shortcut_document_id),
    'missing_shortcut_targets', count(*) FILTER (WHERE d.shortcut_document_id IS NOT NULL AND target.id IS NULL),
    'with_business_record', count(*) FILTER (WHERE d.res_model IS NOT NULL AND d.res_id > 0),
    'business_model_types', count(DISTINCT d.res_model) FILTER (WHERE d.res_id > 0),
    'missing_model_definitions', count(*) FILTER (WHERE d.res_id > 0 AND im.id IS NULL),
    'with_owner', count(d.owner_id), 'with_company', count(d.company_id),
    'missing_owners', count(*) FILTER (WHERE d.owner_id IS NOT NULL AND owner.id IS NULL),
    'missing_companies', count(*) FILTER (WHERE d.company_id IS NOT NULL AND co.id IS NULL),
    'with_link_token', count(*) FILTER (WHERE NULLIF(d.document_token,'') IS NOT NULL),
    'internal_and_link_roles', (SELECT json_agg(json_build_array(internal, via_link, n) ORDER BY internal, via_link)
        FROM (SELECT access_internal internal, access_via_link via_link, count(*) n
              FROM documents_document GROUP BY access_internal, access_via_link) modes),
    'explicit_access_rows', (SELECT count(*) FROM documents_access),
    'missing_access_relations', (SELECT count(*) FROM documents_access acc
        LEFT JOIN documents_document df ON df.id=acc.document_id
        LEFT JOIN res_partner p ON p.id=acc.partner_id WHERE df.id IS NULL OR p.id IS NULL),
    'document_relationship_fingerprint', encode(sha256(convert_to(string_agg(json_build_array(d.id,d.type,d.attachment_id,
        d.folder_id,d.shortcut_document_id,d.res_model,d.res_id,d.owner_id,d.company_id,d.partner_id,
        d.access_internal,d.access_via_link,d.active)::text, chr(10) ORDER BY d.id),'UTF8')), 'hex'),
    'access_relationship_fingerprint', (SELECT encode(sha256(convert_to(string_agg(json_build_array(acc.id,acc.document_id,
        acc.partner_id,acc.role,acc.expiration_date)::text, chr(10) ORDER BY acc.id),'UTF8')), 'hex') FROM documents_access acc)
) FROM documents_document d
LEFT JOIN ir_attachment a ON a.id=d.attachment_id
LEFT JOIN documents_document parent ON parent.id=d.folder_id
LEFT JOIN documents_document target ON target.id=d.shortcut_document_id
LEFT JOIN ir_model im ON im.model=d.res_model
LEFT JOIN res_users owner ON owner.id=d.owner_id
LEFT JOIN res_company co ON co.id=d.company_id
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', help='Isolated copy containing the original Documents tables')
    args = parser.parse_args()
    if len(args.database) > 63 or not re.fullmatch(r'(MANAGEMENT_QA|COMMUNITY)_[A-Z0-9_]+', args.database):
        parser.error('Use a named private validation database')
    result = subprocess.run(
        ['psql', '-XAtq', '--host=/var/run/postgresql', '--set=ON_ERROR_STOP=1', args.database],
        input='BEGIN READ ONLY;\n' + SQL + ';\nROLLBACK;\n', text=True, capture_output=True, check=True,
    )
    print(json.dumps(json.loads(result.stdout), indent=2))


if __name__ == '__main__':
    main()
