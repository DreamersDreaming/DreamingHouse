import unittest
from unittest.mock import patch
from uuid import uuid4

from agent import (
    BOUNDARY,
    DreamInput,
    build_reflection_prompt,
    memory_text,
    similar_memory_query,
    vector_literal,
)
from lambda_function import handler


class DreamInputTests(unittest.TestCase):
    def test_requires_user_and_scene(self):
        with self.assertRaisesRegex(ValueError, "user_id"):
            DreamInput.from_payload({"scene": "a boat"})
        with self.assertRaisesRegex(ValueError, "scene"):
            DreamInput.from_payload({"user_id": str(uuid4())})

    def test_normalizes_explicit_input(self):
        dream = DreamInput.from_payload(
            {"user_id": str(uuid4()), "scene": "  a   blue whale  "}
        )
        self.assertEqual(dream.scene, "a blue whale")

    def test_rejects_non_uuid_user(self):
        with self.assertRaisesRegex(ValueError, "valid UUID"):
            DreamInput.from_payload({"user_id": "u", "scene": "a boat"})


class MemoryBoundaryTests(unittest.TestCase):
    def test_query_is_ownership_scoped(self):
        query = similar_memory_query()
        self.assertIn("WHERE user_id = %(user_id)s::UUID", query)
        self.assertIn("LIMIT 5", query)
        self.assertIn("embedding <=>", query)

    def test_prompt_preserves_safety_contract(self):
        dream = DreamInput(user_id="u", scene="A whale crossed the stars.", emotion="wonder")
        prompt = build_reflection_prompt(dream, [])
        self.assertIn(BOUNDARY, prompt)
        self.assertIn("A whale crossed the stars.", prompt)
        self.assertIn("recurring_patterns must be an empty array", prompt)

    def test_embedding_text_contains_only_supplied_fields(self):
        dream = DreamInput(str(uuid4()), "A whale crossed the stars.", "wonder")
        self.assertEqual(
            memory_text(dream),
            "scene: A whale crossed the stars.\nemotion: wonder",
        )

    def test_vector_literal_requires_1024_dimensions(self):
        with self.assertRaisesRegex(ValueError, "1,024"):
            vector_literal([0.0, 1.0])
        literal = vector_literal([0.0] * 1024)
        self.assertTrue(literal.startswith("[0,"))


class LambdaHandlerTests(unittest.TestCase):
    def test_get_returns_demo_page(self):
        result = handler(
            {"requestContext": {"http": {"method": "GET"}}},
            None,
        )
        self.assertEqual(result["statusCode"], 200)
        self.assertIn("Doream Recall", result["body"])
        self.assertEqual(result["headers"]["cache-control"], "no-store")

    @patch("lambda_function.process_dream")
    def test_success_response_is_private_and_structured(self, process_dream_mock):
        process_dream_mock.return_value = {"status": "ok", "reflection": "{}"}
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://example"}):
            result = handler(
                {"body": '{"user_id":"%s","scene":"a blue whale"}' % uuid4()},
                None,
            )
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["headers"]["cache-control"], "no-store")
        self.assertIn('"status": "ok"', result["body"])

    def test_invalid_payload_returns_400(self):
        result = handler({"body": "not-json"}, None)
        self.assertEqual(result["statusCode"], 400)

    def test_demo_key_is_required_when_configured(self):
        with patch.dict("os.environ", {"DEMO_API_KEY": "secret"}, clear=True):
            result = handler(
                {"body": '{"user_id":"%s","scene":"a blue whale"}' % uuid4()},
                None,
            )
        self.assertEqual(result["statusCode"], 401)


if __name__ == "__main__":
    unittest.main()
