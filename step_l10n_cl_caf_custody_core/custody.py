"""Private custody operations, not an authority trust store or DTE allocator."""
import base64
import binascii

from odoo import _
from odoo.exceptions import AccessError, UserError
from odoo.addons.step_l10n_cl_edi_core.caf import CAFError, normalize_rut, parse_caf
from odoo.addons.step_l10n_cl_edi_core.ted import check_ted_against_caf
from odoo.addons.step_l10n_cl_edi_core.dte_signature import DTEError, verify_signed_dte


MODEL = 'l10n_cl.dte.caf'


def decode_original(value):
    try:
        if isinstance(value, str):
            value = value.encode('ascii')
        if not isinstance(value, bytes) or not value:
            raise ValueError()
        return base64.b64decode(value, validate=True)
    except (ValueError, UnicodeError, binascii.Error):
        raise UserError(_('El archivo original del CAF no está disponible o no tiene un formato válido.')) from None


def parse_original(raw):
    try:
        parsed = parse_caf(raw)
        if parsed.has_private_key:
            parsed.verify_key_pair()
        return parsed
    except CAFError:
        # No XML, secret PEM, personal names or parser internals in UI/errors.
        raise UserError(_('El archivo no cumple el formato de autorización CAF RSA admitido.')) from None


def company_rut(company):
    try:
        value = company.vat or ''
        if value.upper().startswith('CL'):
            value = value[2:]
        return normalize_rut(value)
    except CAFError:
        raise UserError(_('La empresa seleccionada debe tener su RUT chileno válido.')) from None


class CAFCustodyMixin:
    # Ordinary Python mixin; no Odoo model/table or parallel storage. Keep this
    # as a comment: inspect.getdoc() feeds ir.model.info and must retain the
    # original provider's inherited Model documentation.
    # Odoo reassigns registry class bases in _prepare_setup. Adding an instance
    # __dict__ here would change the native recordset layout and reject that
    # reassignment before the original provider can load.
    __slots__ = ()

    def _step_custody_scope(self, operation='read'):
        if self._name != MODEL or self._table != 'l10n_cl_dte_caf':
            raise AccessError(_('La custodia requiere el registro CAF original.'))
        if not (self.env.user.has_group('account.group_account_manager')
                or self.env.user.has_group('stock.group_stock_manager')):
            raise AccessError(_('La custodia CAF requiere el perfil responsable de Contabilidad o Inventario.'))
        self.check_access(operation)
        for record in self:
            # Never infer or backfill a company on an unassigned legacy record.
            if not record.company_id or record.company_id not in self.env.companies:
                raise AccessError(_('El CAF debe pertenecer a una empresa activa y asignada.'))
        return True

    def _step_custody_original_bytes(self):
        self.ensure_one()
        self._step_custody_scope()
        # No parsing, status update, regeneration or normalization while reading
        # history: even an unsupported legacy file remains recoverable exactly.
        return decode_original(self.with_context(bin_size=False).caf_file)

    def step_custody_metadata(self):
        self.ensure_one()
        parsed = parse_original(self._step_custody_original_bytes())
        return {'issuer_rut': parsed.issuer_rut, 'document_type': parsed.document_type,
                'folio_from': parsed.folio_from, 'folio_to': parsed.folio_to,
                'authorization_date': parsed.authorization_date.isoformat(),
                'document_sha256': parsed.document_sha256,
                'authority_verified': False, 'folio_operations_enabled': False,
                'stored_status': self.status or False}

    def step_custody_download(self):
        self.ensure_one()
        self._step_custody_scope()
        if not self.caf_file:
            raise UserError(_('Este registro no contiene un archivo CAF.'))
        return {'type': 'ir.actions.act_url', 'target': 'self',
                'url': '/steps/caf/custody/%s/download' % self.id}

    def step_custody_reserve_folio(self, *args, **kwargs):
        self._step_custody_scope()
        raise UserError(_('La custodia no habilita reservas de folios ni emisión SII.'))

    def step_custody_check_ted(self, file_data):
        """Comprueba el timbre frente al CAF guardado; no habilita emisión."""
        self.ensure_one()
        original = self._step_custody_original_bytes()
        try:
            raw = decode_original(file_data)
        except UserError:
            raise UserError(_('El archivo del timbre no está disponible o no tiene un formato válido.')) from None
        try:
            result = check_ted_against_caf(raw, original)
        except CAFError:
            raise UserError(_('El timbre no coincide con el CAF guardado o su firma y datos no cumplen el formato admitido.')) from None
        self._step_custody_assert_caf_metadata(result.ted._caf)
        # Deliberately no caller-supplied authority map, status transition,
        # persistent verification flag, audit write, attachment or folio use.
        return result.metadata()

    def _step_custody_assert_caf_metadata(self, parsed):
        self.ensure_one()
        document = self.l10n_latam_document_type_id
        document.check_access('read')
        if (not document or document.country_id.code != 'CL'
                or company_rut(self.company_id) != parsed.issuer_rut
                or document.code != str(parsed.document_type)
                or self.start_nb != parsed.folio_from or self.final_nb != parsed.folio_to
                or self.issued_date != parsed.authorization_date):
            raise UserError(_('Los datos del registro CAF no coinciden con su archivo original; la validación no los modifica.'))

    def _step_custody_check_signed_dte(self, file_data, certificate_pin, context):
        """Server-only verification against this CAF, never a signing RPC.

        The explicit certificate pin authenticates only its bytes/key. No
        arbitrary authority map can be supplied here, so CAF authority, signer
        fiscal authorization and folio operations always remain unverified.
        """
        self.ensure_one()
        original = self._step_custody_original_bytes()  # roles/company first
        try:
            result = verify_signed_dte(decode_original(file_data), original, certificate_pin, context)
        except (UserError, DTEError):
            raise UserError(_('El DTE no coincide con el CAF y contexto indicados o su firma, certificado y esquema no son válidos.')) from None
        self._step_custody_assert_caf_metadata(result.ted_verification.ted._caf)
        return result.metadata()

    def step_custody_upload(self, *args, **kwargs):
        # The native reference adds only custody reads; its original upload and
        # original provider class are never replaced by this bridge.
        raise UserError(_('La referencia nativa conserva su carga original; este puente solo permite custodia de lectura.'))
