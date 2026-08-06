"""Validate and summarize the local Mech Arena workbook without third-party packages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m": MAIN_NS}
EXPECTED = {
    "Mechs": ("Mech ID", "Name"),
    "Weapons": ("Weapon ID", "Name"),
    "Pilots": ("Pilot ID", "Name"),
    "Mods": ("Mod ID", "Name"),
    "Best Builds": ("Mech Name", "Weapon 1"),
    "Meta": ("Mech Name", "Weapon 1"),
}


def _shared_strings(archive: ZipFile) -> list[str]:
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t"))
        for item in root.findall("m:si", NS)
    ]


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    value = cell.find("m:v", NS)
    if value is not None:
        return shared[int(value.text)] if cell.attrib.get("t") == "s" else value.text or ""
    if cell.attrib.get("t") == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{{{MAIN_NS}}}t"))
    return ""


def inspect_workbook(path: Path) -> dict:
    with ZipFile(path) as archive:
        shared = _shared_strings(archive)
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            node.attrib["Id"]: node.attrib["Target"]
            for node in relationships.findall(f"{{{PKG_REL_NS}}}Relationship")
        }
        output = {}
        for sheet in workbook.find("m:sheets", NS):
            name = sheet.attrib["name"]
            relationship_id = sheet.attrib[f"{{{REL_NS}}}id"]
            target = targets[relationship_id].lstrip("/")
            target = target if target.startswith("xl/") else f"xl/{target}"
            document = ET.fromstring(archive.read(target))
            rows = document.findall(".//m:sheetData/m:row", NS)
            parsed_rows = [
                [_cell_value(cell, shared) for cell in row.findall("m:c", NS)]
                for row in rows
            ]
            populated = [row for row in parsed_rows if any(value.strip() for value in row)]
            headers = populated[0] if populated else []
            formulas = len(document.findall(".//m:f", NS))
            missing = [header for header in EXPECTED.get(name, ()) if header not in headers]
            output[name] = {
                "physical_rows": len(rows),
                "populated_rows": len(populated),
                "columns": len(headers),
                "headers": headers,
                "formula_cells": formulas,
                "missing_required_headers": missing,
            }
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    args = parser.parse_args()
    report = inspect_workbook(args.workbook)
    errors = [
        f"{name}: missing {', '.join(data['missing_required_headers'])}"
        for name, data in report.items()
        if data["missing_required_headers"]
    ]
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())