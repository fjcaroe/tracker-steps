"""Inspect a saved public SII HTML fixture using the current module parser."""
import argparse
import importlib.util
from pathlib import Path
import sys
import types


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()
    from bs4 import BeautifulSoup
    odoo = types.ModuleType("odoo")
    odoo.fields = types.SimpleNamespace(Date=types.SimpleNamespace(today=lambda: None))
    odoo.models = types.SimpleNamespace(Model=object)
    exceptions = types.ModuleType("odoo.exceptions")
    exceptions.UserError = type("UserError", (Exception,), {})
    sys.modules["odoo"] = odoo
    sys.modules["odoo.exceptions"] = exceptions
    root = Path(__file__).resolve().parents[3]
    source = root / "step_hr_previred_simpledigital/models/impuesto_2da_categoria.py"
    spec = importlib.util.spec_from_file_location("sii_tables", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tables = module._tablas_publicadas(BeautifulSoup(args.html.read_bytes(), "lxml"))
    found = 0
    for period, table in sorted(tables.items()):
        if period[0] == args.year:
            module._valores_mensuales(table)
            print(f"{period[0]}-{period[1]:02d}: parsed")
            found += 1
    if not found:
        raise RuntimeError(f"No published tables for {args.year}")
    print(f"Validated {found} published month(s)")


if __name__ == "__main__":
    main()
