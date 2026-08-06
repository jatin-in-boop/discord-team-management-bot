import unittest
from pathlib import Path

from scripts.validate_mech_arena_workbook import inspect_workbook


class MechArenaWorkbookTest(unittest.TestCase):
    def test_attached_workbook_has_expected_sources(self):
        workbook = Path("attached_assets/MechArena_Database_(1)_1786011874310.xlsx")
        self.assertTrue(workbook.exists())
        report = inspect_workbook(workbook)
        self.assertEqual(set(report), {"Mechs", "Weapons", "Pilots", "Mods", "Best Builds", "Meta"})
        self.assertEqual(report["Mechs"]["populated_rows"], 46)
        self.assertEqual(report["Weapons"]["populated_rows"], 57)
        self.assertEqual(report["Pilots"]["populated_rows"], 37)
        self.assertEqual(report["Mods"]["populated_rows"], 15)
        for data in report.values():
            self.assertEqual(data["missing_required_headers"], [])


if __name__ == "__main__":
    unittest.main()