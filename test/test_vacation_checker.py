from datetime import date

from app.vacation_checker import (
    check_annual_allowance,
    check_back_to_back,
    check_blackout_periods,
    check_block_length,
    check_call_pool_conflict,
    check_no_vacation_rotation,
    check_same_service_conflict,
    check_same_service_repeat,
    check_start_day,
    check_transplant_block,
    check_vacation,
    count_weekdays,
    get_academic_year_bounds,
    normalize_rotation_to_service,
)

# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestCountWeekdays:
    def test_full_week(self):
        # Mon Jan 6 to Fri Jan 10
        assert count_weekdays(date(2025, 1, 6), date(2025, 1, 10)) == 5

    def test_includes_weekend(self):
        # Mon Jan 6 to Sun Jan 12
        assert count_weekdays(date(2025, 1, 6), date(2025, 1, 12)) == 5

    def test_two_weeks(self):
        assert count_weekdays(date(2025, 1, 6), date(2025, 1, 17)) == 10

    def test_single_weekday(self):
        # Wednesday
        assert count_weekdays(date(2025, 1, 8), date(2025, 1, 8)) == 1

    def test_single_weekend(self):
        # Saturday
        assert count_weekdays(date(2025, 1, 11), date(2025, 1, 11)) == 0

    def test_end_before_start(self):
        assert count_weekdays(date(2025, 1, 10), date(2025, 1, 6)) == 0


class TestAcademicYearBounds:
    def test_fall_semester(self):
        assert get_academic_year_bounds(date(2026, 9, 15)) == (
            date(2026, 7, 1),
            date(2027, 6, 30),
        )

    def test_spring_semester(self):
        assert get_academic_year_bounds(date(2027, 3, 1)) == (
            date(2026, 7, 1),
            date(2027, 6, 30),
        )

    def test_july_first(self):
        assert get_academic_year_bounds(date(2026, 7, 1)) == (
            date(2026, 7, 1),
            date(2027, 6, 30),
        )

    def test_june_thirtieth(self):
        assert get_academic_year_bounds(date(2027, 6, 30)) == (
            date(2026, 7, 1),
            date(2027, 6, 30),
        )


class TestNormalizeRotation:
    def test_service_group(self):
        assert (
            normalize_rotation_to_service("Hepatobiliary Surgery")
            == "Surgical Oncology"
        )
        assert normalize_rotation_to_service("Breast") == "Surgical Oncology"
        assert normalize_rotation_to_service("East General Surgery") == "East Services"

    def test_no_group(self):
        assert normalize_rotation_to_service("Burn") == "Burn"
        assert normalize_rotation_to_service("Night Float") == "Night Float"


# ---------------------------------------------------------------------------
# Rule check tests
# ---------------------------------------------------------------------------


class TestBlockLength:
    def test_exactly_seven_days(self):
        # Mon Sep 7 to Sun Sep 13
        result = check_block_length(date(2026, 9, 7), date(2026, 9, 13))
        assert result.passed

    def test_too_short(self):
        result = check_block_length(date(2026, 9, 7), date(2026, 9, 11))
        assert not result.passed

    def test_too_long(self):
        result = check_block_length(date(2026, 9, 7), date(2026, 9, 20))
        assert not result.passed


class TestStartDay:
    def test_monday_start(self):
        result = check_start_day(date(2026, 9, 7))  # Monday
        assert result.passed

    def test_saturday_start(self):
        result = check_start_day(date(2026, 9, 5))  # Saturday
        assert result.passed

    def test_wednesday_start(self):
        result = check_start_day(date(2026, 9, 9))  # Wednesday
        assert not result.passed

    def test_sunday_start(self):
        result = check_start_day(date(2026, 9, 6))  # Sunday
        assert not result.passed


class TestBlackoutPeriods:
    def test_in_july_blackout(self):
        result = check_blackout_periods(date(2026, 7, 10), date(2026, 7, 17))
        assert not result.passed

    def test_in_december_blackout(self):
        result = check_blackout_periods(date(2026, 12, 22), date(2026, 12, 28))
        assert not result.passed

    def test_crossing_year_boundary(self):
        result = check_blackout_periods(date(2026, 12, 30), date(2027, 1, 3))
        assert not result.passed

    def test_in_june_blackout(self):
        result = check_blackout_periods(date(2027, 6, 10), date(2027, 6, 17))
        assert not result.passed

    def test_outside_all_blackouts(self):
        result = check_blackout_periods(date(2026, 9, 1), date(2026, 9, 7))
        assert result.passed

    def test_just_before_july_blackout(self):
        # June 30 is in the June blackout
        result = check_blackout_periods(date(2026, 6, 29), date(2026, 6, 30))
        assert not result.passed

    def test_august_is_clear(self):
        result = check_blackout_periods(date(2026, 8, 1), date(2026, 8, 7))
        assert result.passed


class TestNoVacationRotation:
    def test_on_night_float(self):
        schedule = [
            {
                "rotation": "Night Float",
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 9, 30),
            }
        ]
        result = check_no_vacation_rotation(
            schedule, date(2026, 9, 8), date(2026, 9, 12)
        )
        assert not result.passed

    def test_on_normal_rotation(self):
        schedule = [
            {
                "rotation": "Acute Care Surgery",
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 9, 30),
            }
        ]
        result = check_no_vacation_rotation(
            schedule, date(2026, 9, 8), date(2026, 9, 12)
        )
        assert result.passed


class TestAnnualAllowance:
    def test_under_limit(self):
        existing = [
            {"vac_start": date(2026, 8, 11), "vac_end": date(2026, 8, 15)},  # 5 days
        ]
        # Request 5 more (total 10)
        result = check_annual_allowance(existing, date(2026, 10, 6), date(2026, 10, 10))
        assert result.passed

    def test_at_limit(self):
        existing = [
            {"vac_start": date(2026, 8, 11), "vac_end": date(2026, 8, 22)},  # 10 days
        ]
        # Request 10 more (total 20)
        result = check_annual_allowance(existing, date(2026, 10, 6), date(2026, 10, 17))
        assert result.passed

    def test_over_limit(self):
        existing = [
            # Mon Aug 3 - Fri Aug 14: 10 weekdays
            {"vac_start": date(2026, 8, 3), "vac_end": date(2026, 8, 14)},
            # Mon Aug 17 - Fri Aug 28: 10 weekdays
            {"vac_start": date(2026, 8, 17), "vac_end": date(2026, 8, 28)},
        ]
        # Request 1 more (total 21)
        result = check_annual_allowance(existing, date(2027, 1, 12), date(2027, 1, 12))
        assert not result.passed

    def test_no_existing(self):
        result = check_annual_allowance([], date(2026, 10, 6), date(2026, 10, 10))
        assert result.passed


class TestSameServiceConflict:
    def _make_data(self, other_rotation="Hepatobiliary Surgery"):
        """Create test data where resident 1 requests vacation and resident 2
        is already on vacation."""
        resident_schedule = [
            {
                "resident_id": 1,
                "rotation": "Breast",  # Same service group as HPB
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 9, 30),
            }
        ]
        all_schedules = resident_schedule + [
            {
                "resident_id": 2,
                "rotation": other_rotation,
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 9, 30),
            }
        ]
        all_vacations = [
            {
                "resident_id": 2,
                "resident_name": "Smith",
                "vac_start": date(2026, 9, 8),
                "vac_end": date(2026, 9, 12),
                "vac_type": "vacation",
            }
        ]
        return resident_schedule, all_schedules, all_vacations

    def test_conflict_same_group(self):
        rs, all_s, all_v = self._make_data("Hepatobiliary Surgery")
        result = check_same_service_conflict(
            all_s, all_v, 1, rs, date(2026, 9, 8), date(2026, 9, 12)
        )
        assert not result.passed

    def test_no_conflict_different_service(self):
        rs, all_s, all_v = self._make_data("Burn")
        result = check_same_service_conflict(
            all_s, all_v, 1, rs, date(2026, 9, 8), date(2026, 9, 12)
        )
        assert result.passed

    def test_no_conflict_no_other_vacations(self):
        rs = [
            {
                "resident_id": 1,
                "rotation": "Breast",
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 9, 30),
            }
        ]
        result = check_same_service_conflict(
            rs, [], 1, rs, date(2026, 9, 8), date(2026, 9, 12)
        )
        assert result.passed


class TestCallPoolConflict:
    def test_conflict_same_pool(self):
        # Both on UH Senior Call Pool rotations
        resident_schedule = [
            {
                "resident_id": 1,
                "rotation": "Acute Care Surgery",
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 9, 30),
            }
        ]
        all_schedules = resident_schedule + [
            {
                "resident_id": 2,
                "rotation": "Zollinger Ellison",
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 9, 30),
            }
        ]
        all_vacations = [
            {
                "resident_id": 2,
                "resident_name": "Jones",
                "vac_start": date(2026, 9, 8),
                "vac_end": date(2026, 9, 12),
                "vac_type": "vacation",
            }
        ]
        result = check_call_pool_conflict(
            all_schedules,
            all_vacations,
            1,
            resident_schedule,
            date(2026, 9, 8),
            date(2026, 9, 12),
        )
        assert not result.passed

    def test_no_conflict_different_pool(self):
        resident_schedule = [
            {
                "resident_id": 1,
                "rotation": "Burn",  # PGY2 pool
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 9, 30),
            }
        ]
        all_schedules = resident_schedule + [
            {
                "resident_id": 2,
                "rotation": "Acute Care Surgery",  # UH Senior pool
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 9, 30),
            }
        ]
        all_vacations = [
            {
                "resident_id": 2,
                "resident_name": "Jones",
                "vac_start": date(2026, 9, 8),
                "vac_end": date(2026, 9, 12),
                "vac_type": "vacation",
            }
        ]
        result = check_call_pool_conflict(
            all_schedules,
            all_vacations,
            1,
            resident_schedule,
            date(2026, 9, 8),
            date(2026, 9, 12),
        )
        assert result.passed


class TestBackToBack:
    def test_adjacent_same_service(self):
        existing = [
            {"vac_start": date(2026, 9, 1), "vac_end": date(2026, 9, 5)},
        ]
        schedule = [
            {
                "rotation": "Burn",
                "start_date": date(2026, 8, 1),
                "end_date": date(2026, 9, 30),
            }
        ]
        result = check_back_to_back(
            existing, schedule, 3, date(2026, 9, 8), date(2026, 9, 12)
        )
        assert not result.passed

    def test_adjacent_different_service(self):
        existing = [
            {"vac_start": date(2026, 9, 1), "vac_end": date(2026, 9, 5)},
        ]
        schedule = [
            {
                "rotation": "Burn",
                "start_date": date(2026, 8, 1),
                "end_date": date(2026, 9, 5),
            },
            {
                "rotation": "Acute Care Surgery",
                "start_date": date(2026, 9, 6),
                "end_date": date(2026, 10, 30),
            },
        ]
        result = check_back_to_back(
            existing, schedule, 3, date(2026, 9, 8), date(2026, 9, 12)
        )
        assert result.passed

    def test_no_adjacent(self):
        existing = [
            {"vac_start": date(2026, 8, 11), "vac_end": date(2026, 8, 15)},
        ]
        schedule = [
            {
                "rotation": "Burn",
                "start_date": date(2026, 8, 1),
                "end_date": date(2026, 10, 30),
            }
        ]
        result = check_back_to_back(
            existing, schedule, 3, date(2026, 9, 8), date(2026, 9, 12)
        )
        assert result.passed

    def test_chief_year_final_weeks(self):
        existing = [
            {"vac_start": date(2027, 6, 16), "vac_end": date(2027, 6, 20)},
        ]
        schedule = [
            {
                "rotation": "Burn",
                "start_date": date(2027, 6, 1),
                "end_date": date(2027, 6, 30),
            }
        ]
        result = check_back_to_back(
            existing, schedule, 5, date(2027, 6, 23), date(2027, 6, 27)
        )
        assert result.passed


class TestSameServiceRepeat:
    def test_within_four_weeks(self):
        existing = [
            {"vac_start": date(2026, 9, 8), "vac_end": date(2026, 9, 12)},
        ]
        schedule = [
            {
                "rotation": "Burn",
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 10, 30),
            }
        ]
        result = check_same_service_repeat(
            existing, schedule, date(2026, 9, 22), date(2026, 9, 26)
        )
        assert not result.passed

    def test_beyond_four_weeks(self):
        existing = [
            {"vac_start": date(2026, 9, 1), "vac_end": date(2026, 9, 5)},
        ]
        schedule = [
            {
                "rotation": "Burn",
                "start_date": date(2026, 8, 1),
                "end_date": date(2026, 10, 30),
            }
        ]
        result = check_same_service_repeat(
            existing, schedule, date(2026, 10, 6), date(2026, 10, 10)
        )
        assert result.passed

    def test_different_service(self):
        existing = [
            {"vac_start": date(2026, 9, 8), "vac_end": date(2026, 9, 12)},
        ]
        schedule = [
            {
                "rotation": "Burn",
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 9, 15),
            },
            {
                "rotation": "Acute Care Surgery",
                "start_date": date(2026, 9, 16),
                "end_date": date(2026, 10, 30),
            },
        ]
        result = check_same_service_repeat(
            existing, schedule, date(2026, 9, 22), date(2026, 9, 26)
        )
        assert result.passed


class TestTransplantBlock:
    def test_visiting_on_transplant(self):
        schedule = [
            {
                "rotation": "Transplant",
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 9, 30),
            }
        ]
        result = check_transplant_block(
            schedule, True, date(2026, 9, 8), date(2026, 9, 12)
        )
        assert not result.passed

    def test_non_visiting(self):
        schedule = [
            {
                "rotation": "Transplant",
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 9, 30),
            }
        ]
        result = check_transplant_block(
            schedule, False, date(2026, 9, 8), date(2026, 9, 12)
        )
        assert result.passed

    def test_visiting_not_on_transplant(self):
        schedule = [
            {
                "rotation": "Burn",
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 9, 30),
            }
        ]
        result = check_transplant_block(
            schedule, True, date(2026, 9, 8), date(2026, 9, 12)
        )
        assert result.passed


class TestCheckVacationOrchestrator:
    def test_exempt_pgy1_categorical(self):
        resident = {
            "id": 1,
            "name": "Test",
            "pgy": 1,
            "program": "General Surgery",
            "is_visiting": False,
            "is_prelim": False,
        }
        schedule = [
            {
                "resident_id": 1,
                "rotation": "Vacation",
                "start_date": date(2026, 10, 1),
                "end_date": date(2026, 10, 30),
            }
        ]
        result = check_vacation(
            resident=resident,
            req_start=date(2026, 10, 6),
            req_end=date(2026, 10, 10),
            resident_schedule=schedule,
            resident_vacations=[],
            all_schedules=schedule,
            all_vacations=[],
        )
        assert result.exempt
        assert result.all_passed

    def test_not_exempt_prelim(self):
        resident = {
            "id": 1,
            "name": "Test",
            "pgy": 1,
            "program": "General Surgery",
            "is_visiting": False,
            "is_prelim": True,
        }
        schedule = [
            {
                "resident_id": 1,
                "rotation": "Vacation",
                "start_date": date(2026, 10, 1),
                "end_date": date(2026, 10, 30),
            }
        ]
        result = check_vacation(
            resident=resident,
            req_start=date(2026, 10, 6),
            req_end=date(2026, 10, 10),
            resident_schedule=schedule,
            resident_vacations=[],
            all_schedules=schedule,
            all_vacations=[],
        )
        assert not result.exempt

    def test_all_rules_run(self):
        """Verify all 10 rules are checked for a non-exempt resident."""
        resident = {
            "id": 1,
            "name": "Test",
            "pgy": 3,
            "program": "General Surgery",
            "is_visiting": False,
            "is_prelim": False,
        }
        schedule = [
            {
                "resident_id": 1,
                "rotation": "Burn",
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 9, 30),
            }
        ]
        # Mon Sep 7 to Sun Sep 13: valid 7-day block starting Monday
        result = check_vacation(
            resident=resident,
            req_start=date(2026, 9, 7),
            req_end=date(2026, 9, 13),
            resident_schedule=schedule,
            resident_vacations=[],
            all_schedules=schedule,
            all_vacations=[],
        )
        assert len(result.results) == 10
        assert result.all_passed
