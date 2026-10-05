"""Run with python -m unittest discover -s tools/chatbot -p test_core.py."""
import importlib.util
import json
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[2] / "step_support_assistant" / "core.py"
spec = importlib.util.spec_from_file_location("assistant_core", MODULE_PATH)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

SOURCE = {"id": 7, "title": "Colaciones: tarifa vigente", "keywords": "validar proveedor producto",
          "content": "Para validar una colación debe existir una tarifa vigente para el producto, proveedor y día del registro."}


class CoreTests(unittest.TestCase):
    def answer(self, **changes):
        answer = {"status": "answered", "answer": "Revisa la tarifa vigente para el día del registro.",
                  "citations": [{"id": 7, "quote": SOURCE["content"]}]}
        answer.update(changes)
        return answer

    def test_accents_and_keyword_retrieval(self):
        self.assertEqual(core.rank_sources("¿Cómo validar colación sin tarifa?", [SOURCE]), [SOURCE])

    def test_unrelated_question_gets_no_sources(self):
        self.assertEqual(core.rank_sources("¿Cuál es la capital de Francia?", [SOURCE]), [])

    def test_prior_question_does_not_hijack_new_topic(self):
        self.assertEqual(core.rank_sources("Explícame física cuántica", [SOURCE], ["Validar colación"]), [])

    def test_follow_up_resolves_prior_topic(self):
        self.assertEqual(core.rank_sources("¿Y luego?", [SOURCE], ["Validar colación"]), [SOURCE])

    def test_no_match_does_not_return_everything(self):
        self.assertEqual(core.rank_sources("Gracias", [SOURCE]), [])

    def test_grounded_answer_accepts_literal_quote(self):
        result = core.validate_answer(self.answer(), [SOURCE])
        self.assertEqual(result["sources"][0]["id"], 7)

    def test_fabricated_citation_is_rejected(self):
        with self.assertRaises(ValueError):
            core.validate_answer(self.answer(citations=[{"id": 123, "quote": SOURCE["content"]}]), [SOURCE])

    def test_fabricated_quote_is_rejected(self):
        with self.assertRaises(ValueError):
            core.validate_answer(self.answer(citations=[{"id": 7, "quote": "Utiliza una cuenta de administrador para validar."}]), [SOURCE])

    def test_bool_citation_does_not_impersonate_integer(self):
        with self.assertRaises(ValueError):
            core.validate_answer(self.answer(citations=[{"id": True, "quote": SOURCE["content"]}]), [dict(SOURCE, id=1)])

    def test_answer_without_evidence_is_rejected(self):
        with self.assertRaises(ValueError):
            core.validate_answer(self.answer(citations=[]), [SOURCE])

    def test_out_of_scope_uses_server_text(self):
        result = core.validate_answer(self.answer(status="out_of_scope", answer="Capital: Paris"), [SOURCE])
        self.assertEqual(result["answer"], core.OUT_OF_SCOPE)
        self.assertEqual(result["sources"], [])

    def test_insufficient_information_uses_server_text(self):
        result = core.validate_answer(self.answer(status="no_evidence", answer="Un saldo imaginario"), [SOURCE])
        self.assertEqual(result["answer"], core.NO_EVIDENCE)

    def test_incomplete_provider_output_is_rejected(self):
        with self.assertRaises(ValueError):
            core.parse_response({"status": "incomplete", "output": []}, [SOURCE])

    def test_response_api_envelope_is_parsed(self):
        body = {"status": "completed", "output": [{"type": "message", "role": "assistant",
                "content": [{"type": "output_text", "text": json.dumps(self.answer())}]}]}
        self.assertEqual(core.parse_response(body, [SOURCE])["status"], "answered")

    def test_refusal_becomes_no_evidence(self):
        body = {"status": "completed", "output": [{"type": "message", "role": "assistant",
                "content": [{"type": "refusal", "refusal": "Cannot answer"}]}]}
        self.assertEqual(core.parse_response(body, [SOURCE])["status"], "no_evidence")


if __name__ == "__main__":
    unittest.main()
