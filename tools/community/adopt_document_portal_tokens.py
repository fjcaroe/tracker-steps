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
    assert env.su and re.fullmatch(r"MANAGEMENT_QA_(SYS_LABOR_DOC|SYS_PORTAL|CERRO_CUSTODY|STEPS_CRM)_[A-Z0-9_]+", env.cr.dbname)
    digests, affixes = {}, {}
    for document in env["documents.document"].with_context(active_test=False).search([], order="id"):
        token = document.access_token
        if not isinstance(token, str) or not re.fullmatch(r"[^/?#\s]{1,256}", token):
            raise ValidationError("Existe una referencia externa cuyo formato requiere revisión.")
        original = document.document_token
        if not original or len(original) < 16 or token.count(original) != 1:
            raise ValidationError("La referencia del enlace no se puede reconstruir con el token original.")
        prefix, suffix = token.split(original)
        if len(prefix) + len(suffix) > 64:
            raise ValidationError("El enlace contiene una referencia adicional cuyo formato requiere revisión.")
        digests[str(document.id)] = sha256(token.encode()).hexdigest()
        affixes[str(document.id)] = [prefix, suffix]
    if len(digests) != len(set(digests.values())):
        raise ValidationError("Una referencia externa corresponde a varias identidades.")
    return {"identity": source_identity(env), "digests": digests, "affixes": affixes}


def adopt_portal_references(env, catalog):
    assert env.su and (env.cr.dbname in ("COMMUNITY_SYS_PREVIRED_COHORT_20261127U43C",
                                         "COMMUNITY_SYS_PREVIRED_MODULES_20261127U44FG",
                                         "COMMUNITY_STEPS_CRM_DOC_20261127U43X",
                                         "COMMUNITY_STEPS_CRM_DOC_20261127U44P") or
                       re.fullmatch(r"COMMUNITY_(LIBRARY|PORTAL)_(SYS|CERRO)_[A-Z0-9_]+", env.cr.dbname))
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
    initialized = set(row for row, _ in changed)
    if "affixes" in catalog:
        affixes = {int(row): values for row, values in catalog["affixes"].items()}
        if (affixes.keys() != existing.keys() or any(not isinstance(pair, (list, tuple)) or len(pair) != 2 or
                not all(isinstance(part, str) for part in pair) or len(pair[0]) + len(pair[1]) > 64
                for pair in affixes.values())):
            raise ValidationError("Faltan componentes originales para reconstruir el enlace.")
        row_ids = sorted(affixes)
        env.cr.execute("""
            SELECT d.id,d.step_portal_reference_prefix,d.step_portal_reference_suffix,src.prefix,src.suffix,
                   encode(sha256(convert_to(src.prefix||d.document_token||src.suffix,'UTF8')),'hex')
                     = d.step_portal_reference_hash AS matches
              FROM documents_document d JOIN unnest(%s::integer[],%s::text[],%s::text[]) src(id,prefix,suffix)
                ON d.id=src.id
        """, [row_ids, [affixes[i][0] for i in row_ids], [affixes[i][1] for i in row_ids]])
        changes = []
        for row, prefix, suffix, new_prefix, new_suffix, matches in env.cr.fetchall():
            if not matches or ((prefix, suffix) != (None, None) and (prefix, suffix) != (new_prefix, new_suffix)):
                raise ValidationError("La reconstrucción difiere de la huella del enlace original.")
            if (prefix, suffix) == (None, None):
                changes.append((row, new_prefix, new_suffix))
        if changes:
            env.cr.execute("""
                UPDATE documents_document d SET step_portal_reference_prefix=src.prefix,step_portal_reference_suffix=src.suffix
                  FROM unnest(%s::integer[],%s::text[],%s::text[]) src(id,prefix,suffix) WHERE d.id=src.id
            """, [[r for r, _, _ in changes], [p for _, p, _ in changes], [s for _, _, s in changes]])
            if env.cr.rowcount != len(changes):
                raise ValidationError("No coincidió el número de enlaces preparados para copiar.")
            initialized.update(r for r, _, _ in changes)
    return len(initialized)
