from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from audio_match import normalized_offset, padded_speech_bounds  # noqa: E402
from formats import render_lrc, render_vtt, vtt_time  # noqa: E402
from export_mp3_player import portable_unit, source_disc, source_unit  # noqa: E402
from generate_track_lyrics import reconcile_inferred_overlaps  # noqa: E402
from model import Cue  # noqa: E402
from sources import display_word  # noqa: E402


class AudioMatchTests(unittest.TestCase):
    def test_recovers_known_offset(self) -> None:
        rng = np.random.default_rng(42)
        query = rng.normal(size=800).astype(np.float32)
        source = rng.normal(scale=0.01, size=4_000).astype(np.float32)
        source[1_600:2_400] += query * 0.7
        offset, score = normalized_offset(source, query, 800)
        self.assertAlmostEqual(offset, 2.0, places=3)
        self.assertGreater(score, 0.99)

    def test_reviewed_padding_policy(self) -> None:
        self.assertEqual(padded_speech_bounds((1.0, 2.0), 2.2), (0.9, 2.1))
        self.assertEqual(padded_speech_bounds((1.0, 2.0), 3.0), (0.9, 2.2))


class FormatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cue = Cue(
            book="n1",
            track="1-02",
            entry_id=1,
            kind="word",
            text="青春【せいしゅん】",
            start=0.516,
            end=1.518,
            source_audio="track.mp3",
            source_clip="word.mp3",
            alignment_method="test",
            confidence=1.0,
        )

    def test_lrc_timestamp(self) -> None:
        self.assertIn("[00:00.52]青春【せいしゅん】", render_lrc([self.cue], "n1"))

    def test_vtt_has_start_and_end(self) -> None:
        rendered = render_vtt([self.cue])
        self.assertIn("00:00:00.516 --> 00:00:01.518", rendered)

    def test_long_vtt_time(self) -> None:
        self.assertEqual(vtt_time(3_661.234), "01:01:01.234")

    def test_word_display(self) -> None:
        self.assertEqual(display_word("青春", "せいしゅん"), "青春【せいしゅん】")
        self.assertEqual(display_word("どうしても", "どうしても"), "どうしても")


class ReconciliationTests(unittest.TestCase):
    def cue(self, entry_id: int, method: str, start: float, end: float, text: str) -> Cue:
        return Cue(
            book="n3",
            track="track",
            entry_id=entry_id,
            kind="sentence",
            text=text,
            start=start,
            end=end,
            source_audio="track.mp3",
            source_clip="sentence.mp3",
            alignment_method=method,
            confidence=1.0 if method == "waveform_correlation" else 0.7,
        )

    def test_shared_direct_sentence_is_one_lyric_cue(self) -> None:
        cues = [
            self.cue(404, "waveform_correlation", 10.0, 12.0, "同じ文。"),
            self.cue(405, "waveform_correlation", 10.0, 12.0, "同じ文。"),
        ]
        unresolved = reconcile_inferred_overlaps(cues)
        self.assertEqual(len(cues), 1)
        self.assertEqual(unresolved[0]["review_reasons"], ["shared_sentence_alias_of_verified_neighbor"])

    def test_inference_cannot_reuse_verified_neighbor(self) -> None:
        cues = [
            self.cue(607, "word_anchor_and_silence_inference", 10.0, 12.0, "推定文。"),
            self.cue(608, "waveform_correlation", 10.1, 11.9, "確認済み文。"),
        ]
        unresolved = reconcile_inferred_overlaps(cues)
        self.assertEqual([cue.entry_id for cue in cues], [608])
        self.assertEqual(unresolved[0]["review_reasons"], ["inferred_region_duplicates_verified_neighbor"])


class PlayerExportNamingTests(unittest.TestCase):
    def test_n1_disc_and_unit_come_from_retained_path(self) -> None:
        source = Path(r"D:\audio\Unit7 副詞A\book_Disc2-01.mp3")
        unit = source_unit("n1", source)
        self.assertEqual(unit, "7")
        self.assertEqual(source_disc("n1", source, unit), 2)

    def test_n2_explicit_disc_overrides_unit_boundary(self) -> None:
        source = Path(r"D:\audio\Unit7 名詞C\48 2-1.mp3")
        unit = source_unit("n2", source)
        self.assertEqual(source_disc("n2", source, unit), 2)

    def test_n3_filename_unit_handles_combined_source_folder(self) -> None:
        source = Path(r"D:\audio\Unit6、11 新版\kata_u11_p182-192_id0796-0845.mp3")
        unit = source_unit("n3", source)
        self.assertEqual(unit, "11")
        self.assertEqual(source_disc("n3", source, unit), 2)

    def test_review_unit_is_filename_safe(self) -> None:
        self.assertEqual(portable_unit("4.5"), "4-5")


if __name__ == "__main__":
    unittest.main()
