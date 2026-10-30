"""Pinned public SII schemas. Resolve only these four local reference files."""
import hashlib
from io import BytesIO
from pathlib import Path

from lxml import etree


SCHEMA_SHA256 = {
    'EnvioDTE_v10.xsd': '33ea8dd38c895c359dddbcd21feb5acf8a4717f7f67524a6b0dd9a83d76920eb',
    'DTE_v10.xsd': '85518401b7dddac1bc0b7b99646a1ce353a4afa645344ea5f10af3a2e6676b37',
    'SiiTypes_v10.xsd': 'ce9a84bde70aa9d0f9269d99acd3b0ea81d868022517ac31064b6cdfa0c45bdf',
    'xmldsignature_v10.xsd': '427e3225cd379ae92bae464b892dbf964665af92d453ac61774cffab38b95edb',
}


class SchemaError(ValueError):
    """Code-only exception; do not echo a document or validation log."""


class _PinnedResolver(etree.Resolver):
    def __init__(self, files):
        self.files = files

    def resolve(self, url, public_id, context):
        name = url.removeprefix('memory:///')
        if name not in self.files or url not in (name, 'memory:///' + name):
            raise SchemaError('sii-schema-external-resolution-forbidden')
        # Keep the declared ISO-8859-1 bytes. resolve_string may transcode
        # non-UTF8 schema input on some libxml builds.
        return self.resolve_file(BytesIO(self.files[name]), context, base_url='memory:///' + name)


def official_schema(files=None):
    if files is None:
        root = Path(__file__).with_name('xml_schemas')
        files = {name: (root / name).read_bytes() for name in SCHEMA_SHA256}
    if set(files) != set(SCHEMA_SHA256) or any(type(files[name]) is not bytes
            or hashlib.sha256(files[name]).hexdigest() != digest for name, digest in SCHEMA_SHA256.items()):
        raise SchemaError('sii-schema-source-pin-mismatch')
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    parser.resolvers.add(_PinnedResolver(files))
    try:
        root = etree.fromstring(files['DTE_v10.xsd'], parser, base_url='memory:///DTE_v10.xsd')
        return etree.XMLSchema(root)
    except (etree.XMLSyntaxError, etree.XMLSchemaParseError):
        raise SchemaError('sii-schema-compile-failed') from None


def validate_dte_schema(root):
    if not official_schema().validate(root):
        raise SchemaError('dte-sii-schema-invalid')
