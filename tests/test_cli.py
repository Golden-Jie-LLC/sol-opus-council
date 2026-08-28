from __future__ import annotations

import io
import sys
import unittest
from unittest.mock import patch

from sol_opus_council.cli import _print_json


class CLIOutputTests(unittest.TestCase):
    def test_json_output_reconfigures_windows_legacy_encoding_to_utf8(self) -> None:
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="cp1252")
        with patch.object(sys, "stdout", stream):
            _print_json({"message": "中文审阅通过"})
            stream.flush()
        self.assertIn("中文审阅通过", buffer.getvalue().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
