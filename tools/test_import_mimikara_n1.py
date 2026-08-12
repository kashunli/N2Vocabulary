import unittest

from import_mimikara_n1 import source_notes_markdown, source_reference, structured_terms


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

    def test_source_metadata_is_structured_and_notes_are_not_source_text(self) -> None:
        entry = {
            "page": 10,
            "usage": "名詞",
            "notes": ["review note"],
            "collocations": ["葬式をする"],
            "synonyms": ["葬儀"],
        }

        reference = source_reference(entry, "1-02")
        markdown = source_notes_markdown(entry)

        self.assertEqual(reference, {"title": "N1語彙トレーニング", "page": 10, "cd_track": "1-02"})
        self.assertIn("Usage", markdown)
        self.assertIn("review note", markdown)
        self.assertNotIn("Source", markdown)
        self.assertNotIn("Collocations", markdown)
        self.assertNotIn("Synonyms", markdown)


if __name__ == "__main__":
    unittest.main()
