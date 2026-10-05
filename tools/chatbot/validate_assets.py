"""Validate SCSS using the same libsass compiler that Odoo uses."""
from pathlib import Path
import sys

import sass

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
path = root / "step_support_assistant/static/src/assistant.scss"
sass.compile(string=path.read_text(encoding="utf-8"))
print("ASSISTANT_SCSS_OK")
