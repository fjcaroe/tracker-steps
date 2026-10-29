"""Offline parser for SII's published legacy RECEPCIONDTE upload response.

Source: https://www.sii.cl/factura_electronica/factura_mercado/envio.pdf
OI2003_UPDTE_MDE_1.5, sections 2.1/2.2, figures 2.1-2.3 (pages 8-10).
STATUS 0/TrackID report upload reception, never acceptance of an individual DTE.
This module does not authenticate the source, allocate folios or perform I/O.
"""
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import re

from lxml import etree

from .caf import CAFError, normalize_rut


MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_DETAIL_ERRORS = 100
MAX_TEXT_LENGTH = 8192
_BASE_FIELDS = ('RUTSENDER', 'RUTCOMPANY', 'FILE', 'TIMESTAMP', 'STATUS')


class UploadResponseError(ValueError):
    """Stable codes only; never echo XML, filenames, RUTs or remote errors."""


def _require(value, code):
    if not value:
        raise UploadResponseError(code)


def _rut(value):
    _require(isinstance(value, str), 'rut-format')
    presentation = value.strip().replace('.', '').upper()
    match = re.fullmatch(r'([0-9]{1,9})-([0-9K])', presentation)
    _require(match is not None and int(match[1]) > 0, 'rut-format')
    # Figure 2.3 contains a zero-padded sender. Padding does not change the
    # check-digit identity; original wire bytes are retained separately.
    try:
        return normalize_rut(str(int(match[1])) + '-' + match[2])
    except CAFError:
        raise UploadResponseError('rut-check-digit') from None


def _track(value):
    _require(isinstance(value, str) and re.fullmatch(r'[0-9]{1,32}', value)
             and int(value) > 0, 'track-id-format')
    return value  # Track identifiers are not reformatted or incremented.


def _leaf(node, code):
    _require(not node.attrib and not len(node), code)
    value = (node.text or '').strip()
    _require(bool(value) and len(value) <= MAX_TEXT_LENGTH, code)
    return value


@dataclass(frozen=True)
class UploadResponse:
    sender_rut: str = field(repr=False)
    company_rut: str = field(repr=False)
    filename: str = field(repr=False)
    timestamp_text: str = field(repr=False)
    received_local_time: datetime = field(repr=False)
    status: int
    track_id: str | None = field(repr=False)
    errors: tuple[str, ...] = field(repr=False)
    response_sha256: str
    _original: bytes = field(repr=False)

    @property
    def reports_received(self):
        return self.status == 0 and self.track_id is not None

    @property
    def dte_acceptance(self):
        """No individual-document result is present in this response format."""
        return None

    @property
    def source_authentication_verified(self):
        return False

    def original_bytes(self):
        """Exact, potentially sensitive server payload; never log implicitly."""
        return self._original


def parse_upload_response(xml_bytes):
    """Parse only the upload receipt, including failed uploads and DETAIL.

    Unknown numeric nonzero status is retained as a failure. No retry, business
    state, date/timezone, trust or individual-DTE acceptance is inferred.
    """
    _require(type(xml_bytes) is bytes and 0 < len(xml_bytes) <= MAX_RESPONSE_BYTES,
             'response-size-or-type')
    # Some libxml versions report the declaration's default encoding even
    # after auto-detecting UTF-16. The supported UTF-8/Latin1 profile has no NUL.
    _require(b'\x00' not in xml_bytes, 'response-encoding')
    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True,
            load_dtd=False, recover=False, huge_tree=False, remove_comments=False, remove_pis=False)
        root = etree.fromstring(xml_bytes, parser)
    except (etree.XMLSyntaxError, ValueError):
        raise UploadResponseError('response-xml') from None
    doc = root.getroottree()
    _require(not doc.docinfo.doctype, 'response-dtd')
    _require(doc.docinfo.xml_version == '1.0', 'response-xml-version')
    _require(doc.docinfo.encoding.upper().replace('_', '-') in ('UTF-8', 'ISO-8859-1'),
             'response-encoding')
    _require(root.getprevious() is None and root.getnext() is None, 'response-extra-node')
    for node in root.iter():
        _require(isinstance(node.tag, str), 'response-extra-node')
        _require(not etree.QName(node).namespace and node.prefix is None and not node.nsmap,
                 'response-namespace')
        _require(not node.tail or not node.tail.strip(), 'response-mixed-text')
    _require(root.tag == 'RECEPCIONDTE' and not root.attrib, 'response-root')
    _require(not root.text or not root.text.strip(), 'response-mixed-text')
    names = [node.tag for node in root]
    _require(len(names) == len(set(names)) and set(_BASE_FIELDS) <= set(names)
             and set(names) <= set(_BASE_FIELDS) | {'TRACKID', 'DETAIL'}, 'response-fields')
    nodes = {node.tag: node for node in root}
    sender = _rut(_leaf(nodes['RUTSENDER'], 'sender-format'))
    company = _rut(_leaf(nodes['RUTCOMPANY'], 'company-format'))
    filename = _leaf(nodes['FILE'], 'filename-format')
    timestamp = _leaf(nodes['TIMESTAMP'], 'timestamp-format')
    _require(re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}', timestamp),
             'timestamp-format')
    try:
        local_time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        raise UploadResponseError('timestamp-format') from None
    status_text = _leaf(nodes['STATUS'], 'status-format')
    _require(re.fullmatch(r'[0-9]{1,3}', status_text), 'status-format')
    status = int(status_text)
    track_id = _track(_leaf(nodes['TRACKID'], 'track-id-format')) if 'TRACKID' in nodes else None
    errors = ()
    if 'DETAIL' in nodes:
        detail = nodes['DETAIL']
        _require(not detail.attrib and (not detail.text or not detail.text.strip())
                 and 0 < len(detail) <= MAX_DETAIL_ERRORS, 'detail-format')
        _require(all(node.tag == 'ERROR' for node in detail), 'detail-format')
        errors = tuple(_leaf(node, 'detail-error-format') for node in detail)
    _require((status == 0 and track_id is not None and not errors)
             or (status != 0 and track_id is None), 'status-track-inconsistent')
    return UploadResponse(sender, company, filename, timestamp, local_time, status,
        track_id, errors, hashlib.sha256(xml_bytes).hexdigest(), xml_bytes)


def admit_upload_receipt(response, *, sender_rut, company_rut, filename, existing_track_id=None):
    """Bind a reported reception to caller context, without authenticating SII.

    A failed upload cannot clear a previous TrackID. A different successful
    TrackID is a conflict requiring reconciliation, never an automatic retry.
    The caller must separately authenticate transport and apply original ACLs
    before reading/storing payloads, consulting status or performing any write.
    """
    _require(isinstance(response, UploadResponse), 'response-unparsed')
    fresh = parse_upload_response(response.original_bytes())
    _require(fresh == response, 'response-receipt-mismatch')
    _require(_rut(sender_rut) == fresh.sender_rut, 'sender-mismatch')
    _require(_rut(company_rut) == fresh.company_rut, 'company-mismatch')
    _require(type(filename) is str and filename == fresh.filename, 'filename-mismatch')
    if existing_track_id is not None:
        _track(existing_track_id)
        _require(fresh.track_id == existing_track_id, 'existing-track-conflict')
    _require(fresh.reports_received, 'upload-not-received')
    return fresh
