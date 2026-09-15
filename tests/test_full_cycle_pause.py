"""Tests for scripts/full-cycle.py's pause_before_proceeding()."""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

full_cycle = importlib.import_module("scripts.full-cycle")


class TestPauseBeforeProceeding:
    """#BUG-0099: the post-plan sleep is an interactive abort window and must
    not fire in the unattended cron flow full-cycle is documented for."""

    def test_sleeps_on_a_tty(self):
        with patch.object(sys.stdout, "isatty", return_value=True), \
             patch.object(full_cycle.time, "sleep") as mock_sleep:
            full_cycle.pause_before_proceeding()

        mock_sleep.assert_called_once_with(5)

    def test_does_not_sleep_off_a_tty(self):
        with patch.object(sys.stdout, "isatty", return_value=False), \
             patch.object(full_cycle.time, "sleep") as mock_sleep:
            full_cycle.pause_before_proceeding()

        mock_sleep.assert_not_called()

    def test_seconds_argument_is_respected(self):
        with patch.object(sys.stdout, "isatty", return_value=True), \
             patch.object(full_cycle.time, "sleep") as mock_sleep:
            full_cycle.pause_before_proceeding(seconds=1)

        mock_sleep.assert_called_once_with(1)
