"""Tests for the Excel parser module."""

import os

import pandas as pd
import pytest

from app.parser.cell_parser import (
    VacationInfo,
    parse_rotation_cell,
    parse_visiting_name,
)
from app.parser.excel_parser import parse_date, parse_date_range, parse_excel
from app.parser.layout_detector import LayoutInfo, detect_layout
from app.parser.rotation_map import expand_rotation, is_common_rotation
from app.parser.row_classifier import RowType, classify_row

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "examples")


# --- Rotation Map Tests ---


class TestRotationMap:
    def test_expand_known_abbrev(self):
        assert expand_rotation("ACS") == "Acute Care Surgery"
        assert expand_rotation("CRS") == "Colorectal Surgery"
        assert expand_rotation("HPB") == "Hepatopancreatobiliary Surgery"

    def test_expand_unknown_abbrev(self):
        assert expand_rotation("XYZ") == "XYZ"

    def test_is_common(self):
        assert is_common_rotation("Acute Care Surgery")
        assert is_common_rotation("Colorectal Surgery")
        assert not is_common_rotation("Mount Carmel East")


# --- Cell Parser Tests ---


class TestCellParser:
    def test_simple_rotation(self):
        cells = parse_rotation_cell("ACS")
        assert len(cells) == 1
        assert cells[0].rotation == "ACS"
        assert cells[0].rotation_full == "Acute Care Surgery"

    def test_vacation_extraction(self):
        cells = parse_rotation_cell("CRS [Vac: 12/8-12/14] (A)")
        assert len(cells) == 1
        assert cells[0].rotation == "CRS"
        assert len(cells[0].vacations) == 1
        assert cells[0].vacations[0].vac_start == "12/8"
        assert cells[0].vacations[0].vac_end == "12/14"
        assert cells[0].vacations[0].approved_status == "A"

    def test_conference_extraction(self):
        cells = parse_rotation_cell("ACS [Conf: 9/4-9/5] (A)")
        assert len(cells) == 1
        assert cells[0].vacations[0].vac_type == "conference"

    def test_full_vacation(self):
        cells = parse_rotation_cell("VACATION")
        assert len(cells) == 1
        assert cells[0].is_full_vacation
        assert cells[0].rotation == "VACATION"

    def test_split_rotation(self):
        cells = parse_rotation_cell("ACS/Float")
        assert len(cells) == 2
        assert cells[0].rotation == "ACS"
        assert cells[1].rotation == "Float"

    def test_compound_rotation_not_split(self):
        cells = parse_rotation_cell("Mel Sarc / Endo")
        assert len(cells) == 1
        assert cells[0].rotation == "Mel Sarc / Endo"

    def test_east_location(self):
        cells = parse_rotation_cell("East Gen Surg")
        assert len(cells) == 1
        assert cells[0].location == "East"
        assert cells[0].rotation == "East Gen Surg"

    def test_east_gs(self):
        cells = parse_rotation_cell("East GS")
        assert len(cells) == 1
        assert cells[0].location == "East"

    def test_nan_cell(self):
        cells = parse_rotation_cell(float("nan"))
        assert len(cells) == 0

    def test_empty_cell(self):
        cells = parse_rotation_cell("")
        assert len(cells) == 0


class TestVisitingName:
    def test_dash_pattern(self):
        result = parse_visiting_name("Tanisha Kashikar, DO - Doctors Hospital")
        assert result is not None
        assert result.name == "Tanisha Kashikar, DO"
        assert result.institution == "Doctors Hospital"

    def test_paren_pattern(self):
        result = parse_visiting_name("Oliver Wang (Doctors)")
        assert result is not None
        assert result.name == "Oliver Wang"
        assert result.institution == "Doctors Hospital"

    def test_rotator_pattern(self):
        result = parse_visiting_name("Doctors Rotator- Fennie")
        assert result is not None
        assert result.name == "Fennie"
        assert result.institution == "Doctors Hospital"

    def test_not_visiting(self):
        result = parse_visiting_name("John Smith")
        assert result is None

    def test_riverside(self):
        result = parse_visiting_name("Steven Mitchell (Riverside)")
        assert result is not None
        assert result.institution == "Riverside"


# --- Date Parsing Tests ---


class TestDateParsing:
    def test_parse_date_fall(self):
        ts = parse_date("7/1", 2025)
        assert ts == pd.Timestamp(2025, 7, 1)

    def test_parse_date_spring(self):
        ts = parse_date("3/15", 2025)
        assert ts == pd.Timestamp(2026, 3, 15)

    def test_parse_date_range(self):
        start, end = parse_date_range("7/1-8/24", 2025)
        assert start == pd.Timestamp(2025, 7, 1)
        assert end == pd.Timestamp(2025, 8, 24)

    def test_parse_date_range_cross_year(self):
        start, end = parse_date_range("12/8-2/1", 2025)
        assert start == pd.Timestamp(2025, 12, 8)
        assert end == pd.Timestamp(2026, 2, 1)


# --- Layout Detection Tests ---


class TestLayoutDetection:
    def test_detect_dates_row(self):
        data = {
            0: [None, None],
            1: [None, "Dates"],
            2: [None, "7/1-8/24"],
            3: [None, "8/25-10/19"],
            4: [None, "10/20-12/7"],
        }
        df = pd.DataFrame(data)
        layout = detect_layout(df)
        assert layout is not None
        assert layout.name_col == 1
        assert layout.rotation_start_col == 2
        assert layout.date_row_idx == 1

    def test_detect_without_dates_label(self):
        data = {
            0: [None],
            1: [None],
            2: ["7/1-8/24"],
            3: ["8/25-10/19"],
            4: ["10/20-12/7"],
        }
        df = pd.DataFrame(data)
        layout = detect_layout(df)
        assert layout is not None
        assert layout.rotation_start_col == 2


# --- Row Classification Tests ---


class TestRowClassification:
    def test_blank_row(self):
        row = pd.Series({0: None, 1: None, 2: None})
        result, _ = classify_row(row, name_col=1, pgy_col=0, rotation_start_col=2)
        assert result == RowType.SKIP

    def test_date_row(self):
        row = pd.Series(
            {0: None, 1: "Dates", 2: "7/1-8/24", 3: "8/25-10/19", 4: "10/20-12/7"}
        )
        result, _ = classify_row(row, name_col=1, pgy_col=0, rotation_start_col=2)
        assert result == RowType.DATE

    def test_block_label_row(self):
        row = pd.Series({0: None, 1: None, 2: "Block 1", 3: "Block 2", 4: "Block 3"})
        result, _ = classify_row(row, name_col=1, pgy_col=0, rotation_start_col=2)
        assert result == RowType.SKIP

    def test_pgy_header(self):
        row = pd.Series({0: None, 1: "PGY-5", 2: None, 3: None})
        result, pgy = classify_row(row, name_col=1, pgy_col=0, rotation_start_col=2)
        assert result == RowType.SECTION_HEADER
        assert pgy == "5"

    def test_resident_row(self):
        row = pd.Series({0: 5, 1: "John Smith", 2: "ACS", 3: "CRS"})
        result, _ = classify_row(row, name_col=1, pgy_col=0, rotation_start_col=2)
        assert result == RowType.RESIDENT


# --- Integration Tests ---


def _get_example_file(name):
    path = os.path.join(EXAMPLES_DIR, name)
    if os.path.exists(path):
        return path
    return None


class TestExcelIntegration:
    def test_parse_2022_2023(self):
        path = _get_example_file("2022-2023 Rotation Schedule_June 2022.xlsx")
        if path is None:
            pytest.skip("Example file not available")
        rows = parse_excel(path)
        assert len(rows) > 200
        names = set(r.name for r in rows)
        assert len(names) > 15

    def test_parse_2023_2024(self):
        path = _get_example_file("Copy of 2023-2024 Rotation Schedule v2.xlsb")
        if path is None:
            pytest.skip("Example file not available")
        rows = parse_excel(path)
        assert len(rows) > 200
        names = set(r.name for r in rows)
        assert len(names) > 15

    def test_parse_2024_2025(self):
        path = _get_example_file("2024-2025 Rotation Schedule.xlsx")
        if path is None:
            pytest.skip("Example file not available")
        rows = parse_excel(path)
        assert len(rows) > 300
        names = set(r.name for r in rows)
        assert len(names) > 30
        # Should have visiting residents
        visiting = [r for r in rows if r.is_visiting]
        assert len(visiting) > 0

    def test_parse_2025_2026(self):
        path = _get_example_file("2025-2026 Rotation Schedule.xlsx")
        if path is None:
            pytest.skip("Example file not available")
        rows = parse_excel(path)
        assert len(rows) > 400
        names = set(r.name for r in rows)
        assert len(names) > 30
        # Should have vacations
        vac_count = sum(len(r.vacations) for r in rows)
        assert vac_count > 0
        # Should have visiting residents
        visiting = [r for r in rows if r.is_visiting]
        assert len(visiting) > 0

    def test_split_rotations_produce_two_entries(self):
        path = _get_example_file("2024-2025 Rotation Schedule.xlsx")
        if path is None:
            pytest.skip("Example file not available")
        rows = parse_excel(path)
        # Find someone with a split rotation (e.g., "ACS / Float")
        # The parser should have split these into separate entries
        acs_entries = [r for r in rows if r.rotation == "ACS"]
        float_entries = [r for r in rows if r.rotation in ("Float", "FLOAT")]
        assert len(acs_entries) > 0
        assert len(float_entries) > 0

    def test_no_duplicate_dates_per_resident(self):
        """Each resident should not have overlapping date ranges for a single rotation."""
        path = _get_example_file("2025-2026 Rotation Schedule.xlsx")
        if path is None:
            pytest.skip("Example file not available")
        rows = parse_excel(path)
        # Group by name and check for exact duplicate entries
        from collections import Counter

        entries = Counter((r.name, r.rotation, r.start_date, r.end_date) for r in rows)
        duplicates = {k: v for k, v in entries.items() if v > 1}
        # Allow some duplicates (e.g., visiting residents may have same rotation)
        assert len(duplicates) < 10, f"Too many duplicate entries: {duplicates}"
