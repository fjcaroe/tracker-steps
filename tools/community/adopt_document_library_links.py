"""Adopt the private digest of each native document bookmark on its original restored row."""
import hashlib
import re
from urllib.parse import urlsplit

from odoo.exceptions import ValidationError


def original_identity(env):
    env.cr.execute("""
        SELECT encode(sha256(convert_to(string_agg(json_build_array(id, document_token, url)::text,
               chr(10) ORDER BY id), 'UTF8')), 'hex') FROM documents_document
    """)
    return env.cr.fetchone()[0]


def capture_links(env):
    assert re.fullmatch(r"MANAGEMENT_QA_(SYS_LABOR_DOC|CERRO_CUSTODY)_[A-Z0-9_]+", env.cr.dbname)
    assert env.su
    documents = env["documents.document"].with_context(active_test=False).search([], order="id")
    result = {}
    for row in documents:
        path = urlsplit(row.access_url).path
        if not re.fullmatch(r"/odoo/documents/[^/?#]{1,256}", path):
            raise ValidationError("Formato de enlace histórico desconocido.")
        result[str(row.id)] = hashlib.sha256(path.encode()).hexdigest()
    return {"original_identity": original_identity(env), "hashes": result}


def adopt_links(env, catalog):
    """Call in the migration transaction under the shared environment lock."""
    assert re.fullmatch(r"COMMUNITY_LIBRARY_(SYS|CERRO)_[A-Z0-9_]+", env.cr.dbname) and env.su
    env.cr.execute("LOCK TABLE documents_document IN SHARE ROW EXCLUSIVE MODE")
    if catalog["original_identity"] != original_identity(env):
        raise ValidationError("La referencia de enlaces corresponde a otra biblioteca.")
    env.cr.execute("SELECT id, step_original_url_hash FROM documents_document ORDER BY id")
    rows = dict(env.cr.fetchall())
    hashes = {int(k): v for k, v in catalog["hashes"].items()}
    if (hashes.keys() != rows.keys() or len(set(hashes.values())) != len(rows)
            or not all(re.fullmatch(r"[0-9a-f]{64}", h) for h in hashes.values())):
        raise ValidationError("El catálogo debe identificar una vez cada enlace de la biblioteca.")
    changed = [(digest, row_id) for row_id, digest in hashes.items() if rows[row_id] != digest]
    if any(rows[i] is not None for _, i in changed):
        raise ValidationError("Un enlace adoptado difiere de la referencia original.")
    if changed:
        env.cr.execute("""
            UPDATE documents_document d SET step_original_url_hash = src.link_hash
              FROM unnest(%s::integer[], %s::text[]) AS src(id, link_hash) WHERE d.id = src.id
        """, [[row_id for _, row_id in changed], [digest for digest, _ in changed]])
        if env.cr.rowcount != len(changed):
            raise ValidationError("No se actualizaron todos los enlaces previstos.")
    return len(changed)
