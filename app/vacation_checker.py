from dataclasses import dataclass, field
from datetime import date, timedelta

# Rotations where vacation is never allowed
NO_VACATION_ROTATIONS = {"Night Float", "Intern Simulation"}

# Blackout periods as ((start_month, start_day), (end_month, end_day))
BLACKOUT_PERIODS = [
    ("July 1 - July 30", (7, 1), (7, 30)),
    ("December 20 - January 5", (12, 20), (1, 5)),
    ("June 1 - June 30", (6, 1), (6, 30)),
]

# Rotations grouped as a single service for conflict checks
SERVICE_GROUPS = {
    "Surgical Oncology": {
        "Hepatobiliary Surgery",
        "Melanoma and Sarcoma",
        "Breast",
        "Breast and Endocrine",
    },
    "East Services": {
        "East General Surgery",
        "East ACS",
        "Vascular East",
    },
}

# Call pool name -> set of rotation names belonging to that pool
CALL_POOLS = {
    "UH Senior Call Pool": {
        "Colorectal Surgery",
        "Hepatobiliary Surgery",
        "Breast and Endocrine",
        "Melanoma and Sarcoma",
        "Acute Care Surgery",
        "Zollinger Ellison",
        "Outpatient",
    },
    "UH PGY3 Call Pool": {
        "Zollinger Ellison",
        "Acute Care Surgery",
        "Colorectal Surgery",
        "Surgical ICU",
        "Hepatobiliary Surgery",
    },
    "PGY2 Call Pool": {
        "Burn",
        "Breast",
        "Outpatient Surgical Oncology",
        "Vascular",
        "Thoracic",
        "Endoscopy",
    },
    "Intern Day Call Pool": {
        "Acute Care Surgery",
        "Zollinger Ellison",
        "Colorectal Surgery",
    },
    "East Call Pool": {
        "East General Surgery",
        "Outpatient",
        "Vascular East",
        "East ACS",
    },
}


@dataclass
class RuleResult:
    rule_name: str
    display_name: str
    passed: bool
    message: str
    details: list[str] = field(default_factory=list)


@dataclass
class VacationCheckResult:
    resident_name: str
    resident_pgy: int
    requested_start: date
    requested_end: date
    weekdays_requested: int
    all_passed: bool
    results: list[RuleResult]
    exempt: bool = False
    exempt_reason: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def count_weekdays(start: date, end: date) -> int:
    """Count weekdays (Mon-Fri) in an inclusive date range."""
    if end < start:
        return 0
    total = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            total += 1
        current += timedelta(days=1)
    return total


def get_academic_year_bounds(d: date) -> tuple[date, date]:
    """Return (start, end) of the academic year containing *d*.

    Academic year runs July 1 through June 30.
    """
    if d.month >= 7:
        return date(d.year, 7, 1), date(d.year + 1, 6, 30)
    return date(d.year - 1, 7, 1), date(d.year, 6, 30)


def dates_overlap(s1: date, e1: date, s2: date, e2: date) -> bool:
    """Return True if the two inclusive date ranges overlap."""
    return s1 <= e2 and s2 <= e1


def normalize_rotation_to_service(rotation: str) -> str:
    """Map a rotation to its service group name, or return as-is."""
    for group_name, rotations in SERVICE_GROUPS.items():
        if rotation in rotations:
            return group_name
    return rotation


def get_call_pools_for_rotation(rotation: str) -> list[str]:
    """Return the call pool names that include this rotation."""
    return [
        pool_name
        for pool_name, rotations in CALL_POOLS.items()
        if rotation in rotations
    ]


def _rotation_on_date(schedule: list[dict], d: date) -> str | None:
    """Find the rotation a resident is on for a given date."""
    for entry in schedule:
        if entry["start_date"] <= d <= entry["end_date"]:
            return entry["rotation"]
    return None


def _is_in_blackout(start: date, end: date, year: int) -> list[str]:
    """Return labels of blackout periods that overlap [start, end] in *year*'s
    academic year (July *year* through June *year+1*)."""
    hits: list[str] = []
    for label, (sm, sd), (em, ed) in BLACKOUT_PERIODS:
        if em < sm:  # crosses year boundary (Dec-Jan)
            bs = date(year, sm, sd)
            be = date(year + 1, em, ed)
        elif sm >= 7:
            bs = date(year, sm, sd)
            be = date(year, em, ed)
        else:
            bs = date(year + 1, sm, sd)
            be = date(year + 1, em, ed)
        if dates_overlap(start, end, bs, be):
            hits.append(label)
    return hits


# ---------------------------------------------------------------------------
# Rule checks
# ---------------------------------------------------------------------------


def check_block_length(req_start: date, req_end: date) -> RuleResult:
    """Vacation blocks must be exactly 7 days."""
    length = (req_end - req_start).days + 1
    if length != 7:
        return RuleResult(
            rule_name="block_length",
            display_name="Block Length (7 days)",
            passed=False,
            message=f"Vacation must be exactly 7 days, but requested {length} days.",
        )
    return RuleResult(
        rule_name="block_length",
        display_name="Block Length (7 days)",
        passed=True,
        message="Vacation is exactly 7 days.",
    )


def check_start_day(req_start: date) -> RuleResult:
    """Vacation must start on a Monday (Mon-Sun) or Saturday (Sat-Fri)."""
    day = req_start.weekday()  # 0=Mon, 5=Sat
    if day not in (0, 5):
        day_name = req_start.strftime("%A")
        return RuleResult(
            rule_name="start_day",
            display_name="Start Day (Mon or Sat)",
            passed=False,
            message=(
                f"Vacation starts on {day_name}. "
                f"Must start on Monday (Mon-Sun) or Saturday (Sat-Fri)."
            ),
        )
    pattern = "Mon-Sun" if day == 0 else "Sat-Fri"
    return RuleResult(
        rule_name="start_day",
        display_name="Start Day (Mon or Sat)",
        passed=True,
        message=f"Vacation starts on {req_start.strftime('%A')} ({pattern}).",
    )


def check_blackout_periods(req_start: date, req_end: date) -> RuleResult:
    """No vacation during blackout periods."""
    ay_start, _ = get_academic_year_bounds(req_start)
    hits = _is_in_blackout(req_start, req_end, ay_start.year)
    if hits:
        return RuleResult(
            rule_name="blackout_period",
            display_name="Blackout Period",
            passed=False,
            message="Requested dates overlap with a blackout period.",
            details=[f"Blackout: {h}" for h in hits],
        )
    return RuleResult(
        rule_name="blackout_period",
        display_name="Blackout Period",
        passed=True,
        message="Dates do not fall within any blackout period.",
    )


def check_no_vacation_rotation(
    resident_schedule: list[dict],
    req_start: date,
    req_end: date,
) -> RuleResult:
    """No vacation while on Night Float or Intern Simulation."""
    blocked: list[str] = []
    for entry in resident_schedule:
        if entry["rotation"] in NO_VACATION_ROTATIONS:
            if dates_overlap(
                req_start, req_end, entry["start_date"], entry["end_date"]
            ):
                blocked.append(entry["rotation"])
    if blocked:
        return RuleResult(
            rule_name="no_vacation_rotation",
            display_name="No-Vacation Rotation",
            passed=False,
            message="Vacation is not permitted during these rotations.",
            details=[f"On {r} during requested dates" for r in set(blocked)],
        )
    return RuleResult(
        rule_name="no_vacation_rotation",
        display_name="No-Vacation Rotation",
        passed=True,
        message="Not on a restricted rotation during requested dates.",
    )


def check_annual_allowance(
    existing_vacations: list[dict],
    req_start: date,
    req_end: date,
) -> RuleResult:
    """Total vacation + proposed must not exceed 20 weekdays per academic year."""
    used = sum(count_weekdays(v["vac_start"], v["vac_end"]) for v in existing_vacations)
    requested = count_weekdays(req_start, req_end)
    total = used + requested
    remaining_after = 20 - total

    if total > 20:
        return RuleResult(
            rule_name="annual_allowance",
            display_name="Annual Allowance (20 weekdays)",
            passed=False,
            message=(
                f"Would use {total} of 20 weekdays "
                f"({used} already used + {requested} requested)."
            ),
        )
    return RuleResult(
        rule_name="annual_allowance",
        display_name="Annual Allowance (20 weekdays)",
        passed=True,
        message=(
            f"Would use {total} of 20 weekdays "
            f"({used} used + {requested} requested, "
            f"{remaining_after} remaining)."
        ),
    )


def check_same_service_conflict(
    all_schedules: list[dict],
    all_vacations: list[dict],
    resident_id: int,
    resident_schedule: list[dict],
    req_start: date,
    req_end: date,
) -> RuleResult:
    """No two residents absent from the same service at the same time."""
    conflicts: list[str] = []
    d = req_start
    checked_services: dict[str, set[int]] = {}

    while d <= req_end:
        if d.weekday() >= 5:
            d += timedelta(days=1)
            continue

        my_rotation = _rotation_on_date(resident_schedule, d)
        if my_rotation is None:
            d += timedelta(days=1)
            continue

        my_service = normalize_rotation_to_service(my_rotation)

        for vac in all_vacations:
            if vac["resident_id"] == resident_id:
                continue
            if not (vac["vac_start"] <= d <= vac["vac_end"]):
                continue

            other_rotation = _rotation_on_date(
                [s for s in all_schedules if s["resident_id"] == vac["resident_id"]],
                d,
            )
            if other_rotation is None:
                continue

            other_service = normalize_rotation_to_service(other_rotation)
            if my_service == other_service:
                key = f"{vac['resident_name']} on {other_service}"
                if key not in checked_services:
                    checked_services[key] = set()
                checked_services[key].add(vac["resident_id"])

        d += timedelta(days=1)

    if checked_services:
        conflicts = list(checked_services.keys())
        return RuleResult(
            rule_name="same_service_conflict",
            display_name="Same-Service Conflict",
            passed=False,
            message="Another resident on the same service is already on vacation.",
            details=[f"{c} is also on vacation" for c in conflicts],
        )
    return RuleResult(
        rule_name="same_service_conflict",
        display_name="Same-Service Conflict",
        passed=True,
        message="No other residents on the same service are on vacation.",
    )


def check_call_pool_conflict(
    all_schedules: list[dict],
    all_vacations: list[dict],
    resident_id: int,
    resident_schedule: list[dict],
    req_start: date,
    req_end: date,
) -> RuleResult:
    """No two residents absent from the same call pool at the same time."""
    conflicts: dict[str, str] = {}
    d = req_start

    while d <= req_end:
        if d.weekday() >= 5:
            d += timedelta(days=1)
            continue

        my_rotation = _rotation_on_date(resident_schedule, d)
        if my_rotation is None:
            d += timedelta(days=1)
            continue

        my_pools = get_call_pools_for_rotation(my_rotation)
        if not my_pools:
            d += timedelta(days=1)
            continue

        for vac in all_vacations:
            if vac["resident_id"] == resident_id:
                continue
            if not (vac["vac_start"] <= d <= vac["vac_end"]):
                continue

            other_rotation = _rotation_on_date(
                [s for s in all_schedules if s["resident_id"] == vac["resident_id"]],
                d,
            )
            if other_rotation is None:
                continue

            other_pools = get_call_pools_for_rotation(other_rotation)
            shared_pools = set(my_pools) & set(other_pools)
            for pool in shared_pools:
                key = f"{vac['resident_name']} ({pool})"
                if key not in conflicts:
                    conflicts[key] = pool

        d += timedelta(days=1)

    if conflicts:
        return RuleResult(
            rule_name="call_pool_conflict",
            display_name="Call Pool Conflict",
            passed=False,
            message="Another resident in the same call pool is already on vacation.",
            details=[f"{c} is also on vacation" for c in conflicts],
        )
    return RuleResult(
        rule_name="call_pool_conflict",
        display_name="Call Pool Conflict",
        passed=True,
        message="No call pool conflicts found.",
    )


def check_back_to_back(
    existing_vacations: list[dict],
    resident_schedule: list[dict],
    resident_pgy: int,
    req_start: date,
    req_end: date,
) -> RuleResult:
    """No consecutive vacation weeks unless on different services or PGY-5 final weeks."""
    ay_start, ay_end = get_academic_year_bounds(req_start)
    is_chief_final = resident_pgy == 5 and (ay_end - req_end).days <= 14

    adjacent: list[dict] = []
    for v in existing_vacations:
        gap_before = (req_start - v["vac_end"]).days
        gap_after = (v["vac_start"] - req_end).days
        if 0 < gap_before <= 3 or 0 < gap_after <= 3:
            adjacent.append(v)

    if not adjacent:
        return RuleResult(
            rule_name="back_to_back",
            display_name="Back-to-Back Restriction",
            passed=True,
            message="No adjacent vacation periods found.",
        )

    if is_chief_final:
        return RuleResult(
            rule_name="back_to_back",
            display_name="Back-to-Back Restriction",
            passed=True,
            message="Allowed: PGY-5 in final two weeks of academic year.",
        )

    # Check if the adjacent vacations are on different services
    my_rotation = _rotation_on_date(resident_schedule, req_start)
    my_service = normalize_rotation_to_service(my_rotation) if my_rotation else None

    for v in adjacent:
        other_rotation = _rotation_on_date(resident_schedule, v["vac_start"])
        other_service = (
            normalize_rotation_to_service(other_rotation) if other_rotation else None
        )
        if my_service == other_service:
            return RuleResult(
                rule_name="back_to_back",
                display_name="Back-to-Back Restriction",
                passed=False,
                message="Back-to-back vacation on the same service is not permitted.",
                details=[
                    f"Existing vacation {v['vac_start']} - {v['vac_end']} "
                    f"is on the same service ({my_service})"
                ],
            )

    return RuleResult(
        rule_name="back_to_back",
        display_name="Back-to-Back Restriction",
        passed=True,
        message="Adjacent vacations are on different services.",
    )


def check_same_service_repeat(
    existing_vacations: list[dict],
    resident_schedule: list[dict],
    req_start: date,
    req_end: date,
) -> RuleResult:
    """Two vacations from same service need 4+ clinical weeks separation."""
    my_rotation = _rotation_on_date(resident_schedule, req_start)
    if my_rotation is None:
        return RuleResult(
            rule_name="same_service_repeat",
            display_name="Same-Service Repeat",
            passed=True,
            message="No rotation found for requested dates.",
        )

    my_service = normalize_rotation_to_service(my_rotation)
    min_separation_days = 28  # 4 weeks

    for v in existing_vacations:
        other_rotation = _rotation_on_date(resident_schedule, v["vac_start"])
        if other_rotation is None:
            continue
        other_service = normalize_rotation_to_service(other_rotation)
        if my_service != other_service:
            continue

        # Calculate separation in days
        if v["vac_end"] < req_start:
            gap = (req_start - v["vac_end"]).days
        else:
            gap = (v["vac_start"] - req_end).days

        if gap < min_separation_days:
            return RuleResult(
                rule_name="same_service_repeat",
                display_name="Same-Service Repeat",
                passed=False,
                message=(
                    f"Two vacations from {my_service} must be separated "
                    f"by at least 4 clinical weeks."
                ),
                details=[
                    f"Existing vacation {v['vac_start']} - {v['vac_end']} "
                    f"is only {gap} days away"
                ],
            )

    return RuleResult(
        rule_name="same_service_repeat",
        display_name="Same-Service Repeat",
        passed=True,
        message="No same-service repeat conflicts.",
    )


def check_transplant_block(
    resident_schedule: list[dict],
    is_visiting: bool,
    req_start: date,
    req_end: date,
) -> RuleResult:
    """Outside rotators cannot take vacation during transplant block."""
    if not is_visiting:
        return RuleResult(
            rule_name="transplant_block",
            display_name="Transplant Block",
            passed=True,
            message="Not an outside rotator.",
        )

    for entry in resident_schedule:
        if entry["rotation"] == "Transplant" and dates_overlap(
            req_start, req_end, entry["start_date"], entry["end_date"]
        ):
            return RuleResult(
                rule_name="transplant_block",
                display_name="Transplant Block",
                passed=False,
                message=(
                    "Outside rotators cannot take vacation "
                    "during their transplant block."
                ),
            )

    return RuleResult(
        rule_name="transplant_block",
        display_name="Transplant Block",
        passed=True,
        message="Not on transplant rotation during requested dates.",
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def check_vacation(
    resident: dict,
    req_start: date,
    req_end: date,
    resident_schedule: list[dict],
    resident_vacations: list[dict],
    all_schedules: list[dict],
    all_vacations: list[dict],
) -> VacationCheckResult:
    """Run all vacation rules and return combined result.

    Args:
        resident: dict with id, name, pgy, program, is_visiting, is_prelim
        req_start: proposed vacation start date
        req_end: proposed vacation end date
        resident_schedule: this resident's schedule entries (dicts with
            resident_id, rotation, start_date, end_date)
        resident_vacations: this resident's existing vacations in the
            academic year (dicts with vac_start, vac_end, vac_type)
        all_schedules: all residents' schedule entries overlapping the
            requested dates
        all_vacations: all vacation entries overlapping the requested dates
    """
    weekdays = count_weekdays(req_start, req_end)

    # Check exemption: PGY-1/2 categorical General Surgery on vacation block
    is_categorical = (
        resident["program"] == "General Surgery"
        and not resident["is_prelim"]
        and resident["pgy"] in (1, 2)
    )
    has_vacation_block = any(
        entry["rotation"] == "Vacation"
        for entry in resident_schedule
        if dates_overlap(req_start, req_end, entry["start_date"], entry["end_date"])
    )
    if is_categorical and has_vacation_block:
        return VacationCheckResult(
            resident_name=resident["name"],
            resident_pgy=resident["pgy"],
            requested_start=req_start,
            requested_end=req_end,
            weekdays_requested=weekdays,
            all_passed=True,
            results=[],
            exempt=True,
            exempt_reason=(
                "PGY-1/PGY-2 categorical General Surgery residents "
                "on the vacation block schedule are exempt from "
                "vacation restrictions."
            ),
        )

    results = [
        check_block_length(req_start, req_end),
        check_start_day(req_start),
        check_blackout_periods(req_start, req_end),
        check_no_vacation_rotation(resident_schedule, req_start, req_end),
        check_annual_allowance(resident_vacations, req_start, req_end),
        check_same_service_conflict(
            all_schedules,
            all_vacations,
            resident["id"],
            resident_schedule,
            req_start,
            req_end,
        ),
        check_call_pool_conflict(
            all_schedules,
            all_vacations,
            resident["id"],
            resident_schedule,
            req_start,
            req_end,
        ),
        check_back_to_back(
            resident_vacations,
            resident_schedule,
            resident["pgy"],
            req_start,
            req_end,
        ),
        check_same_service_repeat(
            resident_vacations, resident_schedule, req_start, req_end
        ),
        check_transplant_block(
            resident_schedule, resident["is_visiting"], req_start, req_end
        ),
    ]

    return VacationCheckResult(
        resident_name=resident["name"],
        resident_pgy=resident["pgy"],
        requested_start=req_start,
        requested_end=req_end,
        weekdays_requested=weekdays,
        all_passed=all(r.passed for r in results),
        results=results,
    )
