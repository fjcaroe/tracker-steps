"""Fetch the two original LGPL providers from their exact public Odoo commit and verify every Git object."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import tarfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


COMMIT = "52864b102af6eb4bdedc7910e9cbb6841903a2a3"
TREES = {"hr_timesheet": "7b9b6adbee716a8ff805efbb10659084c1fb8377",
         "project_sms": "e2a37f7d07d09c4dc3009eae9fa8ca6d94eac45c"}
REPO = "https://api.github.com/repos/odoo/odoo/git/"
RAW = "https://raw.githubusercontent.com/odoo/odoo/" + COMMIT + "/addons/"


def fetch(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": "Steps-Community-release-validation"}), timeout=40) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as error:
            if attempt == 2 or isinstance(error, HTTPError) and error.code < 500:
                raise
            time.sleep(2 ** attempt)


def tree_id(entries):
    packed = []
    for item in entries:
        name = item["path"].encode()
        key = name + b"/" if item["type"] == "tree" else name
        packed.append((key, item["mode"].lstrip("0").encode() + b" " + name + b"\0" + bytes.fromhex(item["sha"])))
    content = b"".join(value for key, value in sorted(packed))
    return hashlib.sha1(b"tree " + str(len(content)).encode() + b"\0" + content).hexdigest()


def tree(sha):
    result = json.loads(fetch(REPO + "trees/" + sha))
    if result["truncated"] or tree_id(result["tree"]) != sha:
        raise ValueError("Incomplete official Git tree")
    return result["tree"]


def package(archive):
    commit = json.loads(fetch(REPO + "commits/" + COMMIT))
    assert commit["sha"] == COMMIT
    root = tree(commit["tree"]["sha"])
    addons = next(i["sha"] for i in root if i["path"] == "addons")
    verified = {i["path"]: i["sha"] for i in tree(addons) if i["path"] in TREES}
    assert verified == TREES
    members = []
    for module, sha in TREES.items():
        listing = json.loads(fetch(REPO + "trees/" + sha + "?recursive=1"))
        assert not listing["truncated"] and listing["sha"] == sha
        groups = {"": []}
        for item in listing["tree"]:
            path = Path(item["path"])
            assert not path.is_absolute() and ".." not in path.parts and item["type"] in ("tree", "blob")
            parent = path.parent.as_posix() if path.parent.as_posix() != "." else ""
            groups.setdefault(parent, []).append(dict(item, path=path.name))
            if item["type"] == "blob":
                assert item["mode"] in ("100644", "100755")
                members.append((module + "/" + path.as_posix(), item))
        roots = {i["path"]: i["sha"] for i in listing["tree"] if i["type"] == "tree"}
        assert all(tree_id(children) == (roots[key] if key else sha) for key, children in groups.items())

    def download(member):
        name, item = member
        content = fetch(RAW + name)
        check = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        assert check == item["sha"] and len(content) == item["size"]
        if name.endswith("/__manifest__.py"):
            manifest = ast.literal_eval(content.decode())
            assert manifest["version"] == "1.0" and manifest["license"] == "LGPL-3"
        return name, item, content

    with ThreadPoolExecutor(max_workers=8) as pool, tarfile.open(archive, "x") as out:
        for name, item, content in pool.map(download, sorted(members)):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = int(item["mode"][-3:], 8)
            out.addfile(info, io.BytesIO(content))
    return {"commit": COMMIT, "trees": TREES, "members": len(members),
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.archive), sort_keys=True))
