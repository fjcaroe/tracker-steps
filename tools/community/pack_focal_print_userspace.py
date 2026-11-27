"""Stream the QA operating-system files required by PostgreSQL 12 or the Community PDF runtime."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile


PG = "/usr/lib/postgresql/12"
PYTHON_PACKAGES = """
babel chardet charset_normalizer decorator docutils feedparser geoip2 gevent greenlet jinja2
lxml markupsafe passlib PIL polib psutil psycopg2 pydot OpenSSL PyPDF2 serial dateutil ldap _ldap
werkzeug xlrd xlsxwriter xlwt zeep requests urllib3 reportlab cryptography sass _sass num2words
pytz pypdf ebaysdk ofxparse vobject qrcode idna certifi six pkg_resources setuptools packaging
attrs attr cachetools platformdirs isodate requests_toolbelt requests_file pytz_deprecation_shim
tzdata beautifulsoup4 bs4 soupsieve defusedxml google stdnum freezegun babelmsg pdfminer
cbor2 maxminddb typing_extensions pyparsing pyasn1 pyasn1_modules cffi _cffi_backend pyodbc
psycopg2_binary PyPDF2 pdf2image pdfplumber pypdfium2 yaml _yaml magic pycountry dbfread
pandas numpy openpyxl et_xmlfile phonenumbers xlutils html5lib webencodings unidecode
lxml_html_clean rjsmin _rjsmin libsass docopt sgmllib3k sgmllib unidecode html2text suds
asn1crypto Crypto Cryptodome nacl PIL reportlab dymo werkzeug_routing netaddr distro
zope vobject collections_abc imageio user_agents _distutils_hack pytesseract barcode babel
wheel pkgutil_resolve_name importlib_metadata zipp typing_extensions urllib3_future jmespath
mako markupsafe cryptography_vectors vcr responses passlib_compat erppeek openupgradelib
""".split()


def physical_name(path):
    return Path(os.path.realpath(path.parent)) / path.name


def bundle(stage):
    files = {}
    links = {"bin": "usr/bin", "sbin": "usr/sbin", "lib": "usr/lib", "lib64": "usr/lib64"}
    binaries = set()

    def add(path):
        path = physical_name(Path(path))
        if path.is_symlink():
            resolved = path.resolve(strict=True)
            links[str(path.relative_to("/"))] = os.path.relpath(resolved, path.parent)
            add(resolved)
        elif path.is_file():
            key = str(path.relative_to("/"))
            if key not in files:
                files[key] = path
                with path.open("rb") as stream:
                    if stream.read(4) == b"\x7fELF":
                        binaries.add(path)

    def tree(directory, skip=()):
        root = Path(directory)
        if not root.exists():
            return
        for base, dirs, names in os.walk(root):
            dirs[:] = [part for part in dirs if part not in skip]
            for name in names:
                path = Path(base) / name
                if path.exists() and name not in skip and not name.endswith((".pyc", ".pyo", ".a", ".la")):
                    add(path)

    if stage == "pg":
        for name in ("postgres", "pg_ctl", "initdb", "pg_restore", "pg_dump", "psql", "createdb",
                     "createuser", "pg_isready", "pg_controldata"):
            add(Path(PG, "bin", name))
        for lib in Path(PG, "lib").glob("*.so"):
            if lib.name != "llvmjit.so":
                add(lib)
        tree("/usr/share/postgresql/12")
        tree("/usr/lib/locale")
        tree("/usr/share/zoneinfo")
        for name in ("bash", "dash", "sh", "env", "cat", "ls", "id", "sort", "chmod", "mkdir", "sed",
                     "grep", "locale", "busybox", "getent", "uname", "whoami", "date"):
            add(Path("/usr/bin", name))
        for name in ("libnss_files.so.2", "libnss_dns.so.2", "libnss_compat.so.2", "libresolv.so.2",
                     "libdl.so.2", "libpthread.so.0", "librt.so.1", "libgcc_s.so.1"):
            add(Path("/usr/lib/x86_64-linux-gnu", name))
    elif stage == "odoo":
        for executable in ("/usr/bin/python3.10", "/usr/local/bin/wkhtmltopdf", "/usr/bin/gs",
                           "/usr/bin/fc-list", "/usr/bin/fc-cache", "/usr/bin/pdftoppm", "/usr/bin/pdftotext"):
            add(executable)
        for directory in ("/usr/lib/python3.10", "/usr/share/ghostscript", "/usr/share/fonts",
                          "/usr/local/share/fonts", "/usr/share/color", "/usr/share/fontconfig", "/etc/fonts",
                          "/usr/share/poppler", "/var/lib/ghostscript/CMap", "/usr/share/cups/fonts"):
            tree(directory, ("__pycache__", "test", "tests", "idlelib", "ensurepip"))
        for directory in ("/usr/local/lib/python3.10/dist-packages", "/usr/lib/python3/dist-packages"):
            for name in PYTHON_PACKAGES:
                path = Path(directory, name)
                if path.is_dir():
                    tree(path, ("__pycache__", "test", "tests", "examples"))
                for match in Path(directory).glob(name + ".*"):
                    if match.is_file() and match.suffix in (".py", ".so"):
                        add(match)
            # Metadata is used by Odoo's module dependency checks and entry-point discovery.
            for child in Path(directory).iterdir():
                if child.is_dir() and child.name.endswith((".dist-info", ".egg-info")):
                    project = re.split(r"-(?=\d)", child.name)[0].lower().replace("-", "_")
                    aliases = {"pillow", "python_ldap", "python_dateutil", "pyopenssl", "pyserial",
                               "python_stdnum", "zope.interface", "zope.event", "libsass", "pysocks"}
                    if project in {name.lower() for name in PYTHON_PACKAGES} | aliases:
                        tree(child)
                elif child.name in ("distutils-precedence.pth",):
                    add(child)
        add("/usr/share/misc/magic.mgc")
        tree("/usr/lib/x86_64-linux-gnu/gconv")

    elif stage == "extras":
        extra = {"ldapurl", "ldif", "slapdtest", "cached_property", "appdirs", "ordered_set", "xmltodict", "xmlsec",
                 "requests_file", "requests_toolbelt", "typing_extensions", "pysimplesoap", "multipart", "stdnum",
                 "iso3166", "num2words", "rjsmin", "setuptools_scm", "py3o", "lxml_html_clean", "ofxparse",
                 "html2text", "odf", "xlutils", "pyasn1_modules", "Cryptodome", "binascii", "validators",
                 "backports", "icalendar", "tzlocal", "dateparser", "watchdog", "importlib_resources", "slowapi",
                 "httplib2", "uritemplate", "vobject", "suds", "babel", "geoip2", "maxminddb", "pypdf2", "apsw",
                 "charset_normalizer", "cached_property", "pythonjsonlogger", "html5lib", "pytz_deprecation_shim",
                 "python_barcode", "socks", "zxcvbn", "barcode", "qifparse", "OpenSSL", "Cython", "pdfrw",
                 "lxml_html_clean", "cssselect", "docx", "brotli", "zeep", "requests_file", "platformdirs",
                 "dicttoxml", "simplejson", "jose", "pysaml2", "asn1", "signxml", "oauthlib", "requests_oauthlib",
                 "pikepdf", "inv2", "vaderSentiment", "urllib3_secure_extra", "soupsieve", "tldextract", "olefile"}
        for directory in (Path("/usr/local/lib/python3.10/dist-packages"), Path("/usr/lib/python3/dist-packages")):
            for name in extra:
                path = directory / name
                if path.is_dir():
                    tree(path, ("__pycache__", "test", "tests", "examples"))
                for item in directory.glob(name + ".*"):
                    if item.is_file() and item.suffix in (".py", ".so"):
                        add(item)
    else:
        add("/usr/local/bin/sassc")
        site = Path("/usr/local/lib/python3.10/dist-packages")
        for name in ("sassc.py", "pysassc.py"):
            add(site / name)
        tree(site / "sassutils", ("__pycache__",))
        tree("/var/lib/ghostscript/fonts")
        for name in ("/usr/share/ghostscript/9.50/iccprofiles", "/usr/share/ghostscript/9.50/Resource/CMap"):
            link = Path(name)
            target = link.resolve(strict=True)
            if not target.is_dir() or not (target.is_relative_to("/usr/share/color") or target.is_relative_to("/var/lib/ghostscript")):
                raise ValueError("Unexpected public Ghostscript directory link")
            links[str(link.relative_to("/"))] = os.path.relpath(target, link.parent)
            tree(target)
    seen = set()
    while binaries - seen:
        path = next(iter(binaries - seen))
        seen.add(path)
        # ldd enumerates the full transitive closure of each selected entry point.
        result = subprocess.run(["ldd", str(path)], capture_output=True, text=True)
        if "not found" in result.stdout:
            raise ValueError("Unresolved system library for " + path.name)
        for dep in re.findall(r"(/[^\s]+)\s+\(", result.stdout):
            dep_path = physical_name(Path(dep))
            fresh = set(binaries)
            add(dep_path)
            seen.update(binaries - fresh)

    manifest = {}
    with gzip.GzipFile(fileobj=sys.stdout.buffer, mode="wb", compresslevel=1) as zipped, tarfile.open(fileobj=zipped, mode="w|") as archive:
        for key, path in sorted(files.items()):
            info = archive.gettarinfo(str(path), arcname=key)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o755 if info.mode & 0o111 else 0o644
            # Hard links in distro packages are emitted as independent verified bytes.
            info.type = tarfile.REGTYPE
            info.linkname = ""
            info.size = path.stat().st_size
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                stream.seek(0)
                archive.addfile(info, stream)
            manifest[key] = [info.size, digest.hexdigest(), info.mode]
        data = json.dumps({"stage": stage, "files": manifest, "links": links}, sort_keys=True).encode()
        info = tarfile.TarInfo("steps-runtime-manifest.json")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("pg", "odoo", "extras", "print"))
    bundle(parser.parse_args().stage)
