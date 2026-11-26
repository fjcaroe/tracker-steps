"""Dedicated artifact roots for fenced original-anchor trials."""
from pathlib import Path

VALIDATION_ROOT = Path('/opt/steps-validation')
ANCHOR_DATA_ROOT = Path('/srv/odoo-data/steps-anchor-validation')


def private_artifact(path):
    resolved = Path(path).resolve()
    return resolved.is_relative_to(VALIDATION_ROOT) or (
        resolved.is_relative_to(ANCHOR_DATA_ROOT)
        and resolved != ANCHOR_DATA_ROOT
        and resolved.relative_to(ANCHOR_DATA_ROOT).parts[0].startswith('community-original-handover-')
    )
