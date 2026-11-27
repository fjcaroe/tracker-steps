"""Bind external sharing references to original document rows using digests from a private native copy."""
from hashlib import sha256
import re

from odoo.exceptions import ValidationError


def source_identity(env):
    env.cr.execute("""
        SELECT encode(sha256(convert_to(string_agg(json_build_array(id, document_token)::text,
                       chr(10) ORDER BY id),'UTF8')),'hex') FROM documents_document
    """)
    return env.cr.fetchone()[0]


def capture_portal_references(env):
    assert env.su and re.fullmatch(r"MANAGEMENT_QA_(SYS_LABOR_DOC|SYS_PORTAL|CERRO_CUSTODY)_[A-Z0-9_]+", env.cr.dbname)
    digests = {}
    for document in env["documents.document"].with_context(active_test=False).search([], order="id"):
        token = document.access_token
        if not isinstance(token, str) or not re.fullmatch(r"[^/?#\s]{1,256}", token):
            raise ValidationError("Existe una referencia externa cuyo formato requiere revisión.")
        digests[str(document.id)] = sha256(token.encode()).hexdigest()
    if len(digests) != len(set(digests.values())):
        raise ValidationError("Una referencia externa corresponde a varias identidades.")
    return {"identity": source_identity(env), "digests": digests}


def adopt_portal_references(env, catalog):
    assert env.su and re.fullmatch(r"COMMUNITY_(LIBRARY|PORTAL)_(SYS|CERRO)_[A-Z0-9_]+", env.cr.dbname)
    env.cr.execute("LOCK TABLE documents_document IN SHARE ROW EXCLUSIVE MODE")
    if source_identity(env) != catalog["identity"]:
        raise ValidationError("Las identidades y referencias difieren de la copia nativa.")
    env.cr.execute("SELECT id, step_portal_reference_hash FROM documents_document ORDER BY id")
    existing = dict(env.cr.fetchall())
    digests = {int(row): value for row, value in catalog["digests"].items()}
    if (existing.keys() != digests.keys() or len(digests) != len(set(digests.values())) or
            not all(re.fullmatch(r"[a-f0-9]{64}", value) for value in digests.values())):
        raise ValidationError("El catálogo de accesos externos está incompleto.")
    changed = [(row, value) for row, value in digests.items() if existing[row] != value]
    if any(existing[row] is not None for row, _ in changed):
        raise ValidationError("Una referencia externa adoptada difiere de su original.")
    if changed:
        env.cr.execute("""
            UPDATE documents_document d SET step_portal_reference_hash=src.digest
              FROM unnest(%s::integer[],%s::text[]) src(id,digest) WHERE d.id=src.id
        """, [[row for row, _ in changed], [value for _, value in changed]])
        if env.cr.rowcount != len(changed):
            raise ValidationError("El número de referencias adoptadas no coincide.")
    return len(changed)
