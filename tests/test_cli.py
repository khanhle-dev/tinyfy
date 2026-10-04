import tempfile
import unittest
from pathlib import Path

from tinyfy.cli import main


class CompressTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_text_roundtrip(self):
        src = self.dir / "a.txt"
        src.write_text("hello world\n" * 10000)
        for fmt in ("xz", "gz", "zst", "zip"):
            out = self.dir / fmt
            self.assertEqual(main([str(src), "-f", fmt, "-o", str(out)]), 0)
            archive = out / f"a.txt.{fmt}"
            self.assertLess(archive.stat().st_size, src.stat().st_size)
            self.assertEqual(main(["-x", str(archive), "-o", str(out / "ex")]), 0)
            self.assertEqual((out / "ex" / "a.txt").read_text(), src.read_text())

    def test_jpeg_smaller_same_dir(self):
        from PIL import Image
        src = self.dir / "p.jpg"
        Image.effect_mandelbrot((800, 600), (-2, -1.2, 1, 1.2), 100).convert("RGB").save(src, quality=98)
        self.assertEqual(main([str(src)]), 0)
        out = self.dir / "p.min.jpg"
        self.assertLess(out.stat().st_size, src.stat().st_size)

    def test_dir_each_keeps_unknown_files(self):
        d = self.dir / "d"
        d.mkdir()
        (d / "x.bin").write_bytes(b"\0" * 1000)
        self.assertEqual(main([str(d), "--each"]), 0)
        self.assertEqual((self.dir / "d.min" / "x.bin").read_bytes(), b"\0" * 1000)

    def test_output_as_file_and_rerun_overwrites(self):
        src = self.dir / "log.txt"
        src.write_text("log line\n" * 10000)
        out = self.dir / "results" / "small.gz"
        for _ in range(2):
            self.assertEqual(main([str(src), "-o", str(out)]), 0)
            self.assertTrue(out.is_file())
        import gzip
        self.assertEqual(gzip.decompress(out.read_bytes()).decode(), src.read_text())
        # extract to an exact file; re-running overwrites it
        back = self.dir / "back.txt"
        for _ in range(2):
            self.assertEqual(main(["-x", str(out), "-o", str(back)]), 0)
        self.assertEqual(back.read_text(), src.read_text())

    def test_output_trailing_slash_is_dir(self):
        src = self.dir / "a.txt"
        src.write_text("a" * 10000)
        self.assertEqual(main([str(src), "-o", str(self.dir / "out.v2") + "/"]), 0)
        self.assertTrue((self.dir / "out.v2" / "a.txt.xz").is_file())

    def test_output_file_rejects_many_inputs(self):
        with self.assertRaises(SystemExit):
            main([str(self.dir), str(self.dir), "-o", str(self.dir / "x.pdf")])

    def test_missing_file_fails(self):
        self.assertEqual(main([str(self.dir / "nope")]), 1)


if __name__ == "__main__":
    unittest.main()
