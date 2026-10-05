"""Create a code-only archive outside the checkout. No env/config/user data included."""
import argparse
import ast
from pathlib import Path
import tarfile
import tempfile
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = args.output or Path(tempfile.gettempdir()) / "steps_assistant_release.tar.gz"
    if output.resolve().is_relative_to(root):
        parser.error("The release archive must be outside the checkout")
    allowed = {".py", ".xml", ".csv", ".js", ".scss", ".svg", ".png", ".md"}
    files = [path for module in (root / "step_support_assistant", root / "step_support_assistant_knowledge")
             for path in module.rglob("*") if path.is_file() and path.suffix in allowed
             and "__pycache__" not in path.parts]
    for path in files:
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8"), str(path))
        elif path.suffix in {".xml", ".svg"}:
            ET.parse(path)
    with tarfile.open(output, "w:gz") as archive:
        for path in sorted(files):
            archive.add(path, arcname=path.relative_to(root))
    import hashlib
    print(str(output))
    print("SHA256=" + hashlib.sha256(output.read_bytes()).hexdigest())
    print(f"{len(files)} validated source files")


if __name__ == "__main__":
    main()
