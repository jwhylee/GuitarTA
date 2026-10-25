import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from guitarta.services.audio_processor import AudioProcessingError, AudioProcessor


class StemCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.processor = AudioProcessor(Path(self.temp_dir.name))
        self.paths = self.processor._note_paths(1)
        self.paths["stems_dir"].mkdir(parents=True)
        self.stem = self.paths["stems_dir"] / "bass.wav"
        self.stem.write_bytes(b"intermediate audio")
        for key in ("original", "bass_removed", "guitar_removed", "drums_only"):
            self.write_wav(self.paths[key])

    def write_wav(self, path, frames=4410):
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(44100)
            audio.writeframes(b"\0" * frames * 4)

    def test_complete_outputs_remove_only_stems(self):
        originals = {key: self.paths[key].read_bytes() for key in (
            "original", "bass_removed", "guitar_removed", "drums_only"
        )}
        playback = self.paths["note_dir"] / "playback_bass_removed.mp4"
        playback.write_bytes(b"existing playback")
        self.assertEqual(self.processor.cleanup_note_stems(1), 18)
        self.assertFalse(self.paths["stems_dir"].exists())
        for key, data in originals.items():
            self.assertEqual(self.paths[key].read_bytes(), data)
        self.assertEqual(playback.read_bytes(), b"existing playback")
        self.assertEqual(self.processor.cleanup_note_stems(1), 0)

    def test_missing_output_keeps_stems(self):
        self.paths["drums_only"].unlink()
        self.assertEqual(self.processor.cleanup_note_stems(1), 0)
        self.assertTrue(self.stem.exists())

    def test_truncated_output_keeps_stems(self):
        path = self.paths["bass_removed"]
        path.write_bytes(path.read_bytes()[:-4])
        self.assertEqual(self.processor.cleanup_note_stems(1), 0)
        self.assertTrue(self.stem.exists())

    def test_short_output_keeps_stems(self):
        self.write_wav(self.paths["guitar_removed"], frames=44100)
        self.assertEqual(self.processor.cleanup_note_stems(1), 0)
        self.assertTrue(self.stem.exists())

    def test_stale_output_keeps_stems(self):
        original_time = self.paths["original"].stat().st_mtime
        os.utime(self.paths["bass_removed"], (original_time - 1, original_time - 1))
        self.assertEqual(self.processor.cleanup_note_stems(1), 0)
        self.assertTrue(self.stem.exists())

    def test_current_outputs_are_not_regenerated_after_cleanup(self):
        source = Path(self.temp_dir.name) / "source.mp4"
        source.write_bytes(b"video")
        original_time = self.paths["original"].stat().st_mtime
        os.utime(source, (original_time - 1, original_time - 1))
        with patch.object(self.processor, "_split_stems") as split:
            self.processor.prepare_note_audio(1, str(source))
            self.processor.prepare_note_audio(1, str(source))
            split.assert_not_called()
        self.assertFalse(self.paths["stems_dir"].exists())

    def test_failed_generation_keeps_stems(self):
        source = Path(self.temp_dir.name) / "source.mp4"
        source.write_bytes(b"video")
        original_time = self.paths["original"].stat().st_mtime
        os.utime(source, (original_time - 1, original_time - 1))
        self.paths["drums_only"].unlink()
        with patch.object(self.processor, "_split_stems", side_effect=AudioProcessingError("failed")):
            with self.assertRaises(AudioProcessingError):
                self.processor.prepare_note_audio(1, str(source))
        self.assertTrue(self.stem.exists())


if __name__ == "__main__":
    unittest.main()
