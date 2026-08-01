import unittest

from import_mimikara_n1 import detail_markdown, structured_terms


class MimikaraN1StructuredTermTests(unittest.TestCase):
    def test_relationships_become_individual_categorized_terms(self) -> None:
        entry = {
            "collocations": ["葬式をする", "葬式を出す", "葬式をする"],
            "synonyms": ["葬儀"],
            "related": ["墓", "墓参り"],
        }

        self.assertEqual(
            structured_terms(entry),
            [
                ("連", "葬式をする"),
                ("連", "葬式を出す"),
                ("類", "葬儀"),
                ("関連", "墓"),
                ("関連", "墓参り"),
            ],
        )

    def test_structured_relationships_are_not_duplicated_in_markdown(self) -> None:
        entry = {
            "page": 10,
            "usage": "名詞",
            "notes": ["review note"],
            "collocations": ["葬式をする"],
            "synonyms": ["葬儀"],
        }

        markdown = detail_markdown(entry, "1-02")

        self.assertIn("Usage", markdown)
        self.assertIn("review note", markdown)
        self.assertNotIn("Collocations", markdown)
        self.assertNotIn("Synonyms", markdown)


if __name__ == "__main__":
    unittest.main()
