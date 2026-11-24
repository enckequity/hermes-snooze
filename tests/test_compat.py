"""Contract test: every engine name the runtime code imports is listed in compat.py.

compat.py is run with the engine's own Python (in CI and in the TeamShift image build) and fails when one of
those names disappears. This test keeps that list complete, so a new private import cannot slip past it.
"""

import ast
import unittest
from pathlib import Path
from unittest import mock

from snooze import compat

ROOT = Path(__file__).resolve().parent.parent
ENGINE_PREFIXES = ("tools", "agent", "plugins", "gateway", "hermes_constants", "hermes_cli", "cron")


def engine_imports():
    found = set()
    for path in ROOT.glob("*.py"):
        if path.name == "compat.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                if node.module.split(".")[0] in ENGINE_PREFIXES:
                    found.update((node.module, alias.name) for alias in node.names)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in ENGINE_PREFIXES, f"{path.name}: import {alias.name}"
    return found


NAMES = [("json", "loads"), ("json", "no_such_name"), ("no_such_mod", "x"), ("no_such_mod|json", "dumps")]


class CompatContractTest(unittest.TestCase):
    def test_every_engine_import_is_checked(self):
        listed = {(alt, name.split(".")[0]) for module, name in compat.HERMES_NAMES for alt in module.split("|")}
        missing = engine_imports() - listed
        self.assertFalse(missing, f"add these to compat.HERMES_NAMES: {sorted(missing)}")

    def test_finds_the_private_send_path(self):
        self.assertIn(("gateway.outbound.send", "send_message_tool"), engine_imports())
        self.assertIn(("tools.send_message_tool", "send_message_tool"), engine_imports())
        self.assertIn(("agent.estop", "is_engaged"), engine_imports())

    def test_missing_names_are_reported(self):
        with mock.patch.object(
            compat,
            "HERMES_NAMES",
            NAMES,
        ):
            with mock.patch.object(compat, "HERMES_HOOKS", []):
                failed = compat.failed_names()
        self.assertEqual(sorted(failed), ["json.no_such_name", "no_such_mod.x"])


if __name__ == "__main__":
    unittest.main()
