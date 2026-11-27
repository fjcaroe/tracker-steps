"""Measure historical signing-field display with original operators and blank synthetic images."""
import base64
from collections import Counter
import hashlib
from io import BytesIO
from itertools import product
import json

from PIL import Image


def signing_matrix(shell, move_types):
    user = shell["res.users"].browse(6)
    scope = shell(user=user.id, su=False, context={"allowed_company_ids": [user.company_id.id]})
    assert not scope.su
    with BytesIO() as buffer:
        Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
        sample = base64.b64encode(buffer.getvalue())
    signed = scope["res.users"].new({"sign_signature": sample})
    empty = scope["res.users"].new({})
    result = []
    cases = product((False, True), (False, True), ("no", "blank", "sample"), move_types, ("draft", "posted", "cancel"))
    for enabled, configured, label, move_type, state in cases:
        company = scope["res.company"].new({"name": "Offline reference test", "sign_invoice": enabled,
                                            "signing_user": signed if configured else False})
        move = scope["account.move"].new({"company_id": company, "move_type": move_type, "state": state,
                                          "signing_user": {"no": False, "blank": empty, "sample": signed}[label]})
        value = move.signature
        result.append([enabled, configured, label, move_type, state, bool(move.show_signature_area), bool(value), value == sample])
    return result


def check_signing(shell, expected_receipts):
    types = ("out_invoice", "out_refund", "in_invoice", "in_refund", "entry")
    synthetic = signing_matrix(shell, types)
    user = shell["res.users"].browse(6)
    actual = Counter()
    for company in user.company_ids.filtered("active"):
        scope = shell(user=user.id, su=False, context={"allowed_company_ids": [company.id]})
        moves = scope["account.move"].search([("company_id", "=", company.id)])
        for move in moves:
            key = (move.move_type, move.state, bool(move.signing_user), bool(move.show_signature_area), bool(move.signature))
            actual[str(key)] += 1
    proof = json.dumps({"synthetic": synthetic, "original": dict(actual)}, sort_keys=True, separators=(",", ":")).encode()
    signature = hashlib.sha256(proof).hexdigest()
    assert signature == "d14d2f6bf28a943b8f78f621e12e26ab7dc5ce08ae5e1fdba0471cc875ddb9bf"
    receipts = signing_matrix(shell, ("out_receipt", "in_receipt"))
    assert receipts == expected_receipts
    return {"signed_result": signature, "original_documents": sum(actual.values()), "synthetic_cases": len(synthetic),
            "receipt_cases": len(receipts)}
