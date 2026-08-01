import unittest

from translate_n1_examples_en import parse_content, prompt_for


class N1EnglishTranslationTests(unittest.TestCase):
    def test_json_code_fence_is_tolerated_but_parsed_strictly(self) -> None:
        parsed = parse_content('```json\n{"items":[{"id":"1:2","translation_en":"grave"}]}\n```')
        self.assertEqual(parsed["items"][0]["translation_en"], "grave")

    def test_prompt_includes_relation_context_and_stable_id(self) -> None:
        prompt = prompt_for([
            {
                "id": "4501:4",
                "headword": "葬式",
                "reading": "そうしき",
                "meaning_en": "funeral",
                "kind": "related_term",
                "category": "連",
                "text": "葬式をする",
            }
        ])
        self.assertIn('"id": "4501:4"', prompt)
        self.assertIn('"category": "連"', prompt)
        self.assertIn('"text": "葬式をする"', prompt)


if __name__ == "__main__":
    unittest.main()
