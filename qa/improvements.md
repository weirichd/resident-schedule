# Cross-Persona Improvements — Ranked

Synthesis of findings from all 6 QA personas (run 2026-05-12). Issues are deduplicated and ranked by **impact** (severity × number of personas affected × confidence of harm), with a rough **effort** estimate so we can pick what to do first.

Effort scale: **XS** = one-line / template tweak, **S** = single function, **M** = multi-file feature, **L** = new view + data work.

---

## Tier 1 — Correctness bugs (the tool actively misleads users)

| # | Issue | Personas | Effort | Where |
|---|---|---|---|---|
| 1 | **Asymmetric prefix-match on rotation Current section.** `current = [e for e in entries if e["rotation"].startswith(rotation_name)]` — `/rotation/Breast/` silently absorbs Breast-and-Endocrine residents; `/rotation/Breast and Endocrine/` shows zero. Same risk for Outpatient / Outpatient Surgical Oncology and any other prefix pair. The Current and Coming Next sections on the *same* page also use different filters (prefix vs exact). | Breast Attending | XS | `app/app.py:315` |
| 2 | **Categorical PGY-1/2 vacation-block exemption is dead code.** `app/vacation_checker.py:617` looks for `entry["rotation"] == "Vacation"` but the parser emits 0 Vacation rows. Effect: every categorical PGY-1/2's built-in block is counted toward Annual Allowance, *and* the during-block exemption never fires. The whole code path is unreachable. | Vacation Planner | M | `parse_schedule.py:write_to_db`, `app/vacation_checker.py:611-637`, plus a backfill migration |
| 3 | **Parser is creating duplicate vacation rows.** Confirmed: Grant Sajdak has overlapping pairs (Sep 14–20 *and* Sep 14–18; June 7–13 *and* June 7–11). Inflates Annual Allowance counts, double-counts conflicts, and likely affects others — needs a sweep of the table. | Service Chief | S | `parse_schedule.py` parsing/dedup + one-time DB cleanup |
| 4 | **`/vacation_check/` accepts garbage input silently.** Invalid `resident_id` re-renders the empty form with no error. Inverted date ranges (`end < start`) run rules and produce "requested -5 days." Date inputs have no `min`/`max`. | Vacation Planner | S | `app/app.py:387` + `app/templates/vacation_checker.html` |
| 5 | **`/resident/?name=...` returns raw FastAPI 422 JSON** (`{"detail":[{"type":"missing",...}]}`) on any malformed query. Anyone sharing a stale link gets a wall of JSON. | Intern | S | `app/app.py` `@app.exception_handler(RequestValidationError)` |

---

## Tier 2 — Discoverability blockers (the tool is unusable for the persona's actual goal)

| # | Issue | Personas | Effort | Where |
|---|---|---|---|---|
| 6 | **`/` empty-state on between-AY dates.** May 12 (today) shows "No data was found." For a new intern landing here, this *is* the first impression. Fix: fall through to the closest dated schedule with a banner ("Showing 2026-07-01 — the next available date") and/or surface the data-range hint. | Intern, Post-call, Breast Attending (all hit it before pivoting) | S | `app/app.py` `/`, `home.html` |
| 7 | **No date input on the rotation page.** The endpoint already honors `?date=`, but only a URL-fluent user can use it. The post-call resident wants "tomorrow" and can't get it; the chief wants "next month" and has to type the URL. | Post-call, Breast Attending, Service Chief | XS | `app/templates/rotation_detail.html` (date input that submits with `?date=`) |
| 8 | **Tom Select optgroup headers don't render.** PGY 1 / PGY 2 / PGY 3 / PGY 4 / PGY 5 markers are correct in the HTML, but the Tom Select config is missing `optgroupField`. Affects the resident picker (153 entries flat) AND the vacation checker dropdown. | Intern, Vacation Planner | XS | `resident_picker.html`, `vacation_checker.html` (one-line config each) |

---

## Tier 3 — Cross-cutting polish that every persona feels

| # | Issue | Personas | Effort | Where |
|---|---|---|---|---|
| 9 | **No year in date columns.** "November 01" / "March 31" — ambiguous when the persona is looking forward across an academic-year boundary. Hit by every persona; especially acute for the visiting resident planning a single block 9 months out. | All 6 | XS | `app/app.py:prepare_table()` |
| 10 | **Off-service rotators are visually nameless.** In the picker they're last-name-only with no program label (Anesthesia, Urology, Plastics, Ortho). In tables their program shows as small unlabeled sub-text. Doctors Hospital visitors get `(Doctors Hospital)` so the asymmetry feels like a second-class data treatment. | Visiting, Intern, Post-call, Service Chief, Breast Attending | S | `_pgy_grouped_residents()` + `prepare_table()` + templates |
| 11 | **`include_visiting` toggle is semantically ambiguous.** Means "outside-institution" today (Doctors Hospital). Persona expectations: "off-service department rotators" (Anesthesia/Urology/Plastics/Ortho). Also the toggle is rendered on the single-resident page where it does nothing. | Visiting, Post-call, Intern, Breast Attending | M | Rename + (optionally) split into two toggles; touches `app/app.py`, several templates, possibly Resident model semantics |

---

## Tier 4 — Forward-visibility features (the rotation page can't answer planning questions)

| # | Issue | Personas | Effort | Where |
|---|---|---|---|---|
| 12 | **Coming Next is one block per PGY.** Real chief / attending question is "the next 2-3 months." Today they have to URL-scrub block by block and reassemble in their head. | Service Chief, Breast Attending | M | `app/app.py:get_coming_next_entries`, new "Look Ahead" template section, configurable window default 90 days |
| 13 | **Future rotators' vacations are invisible.** A chief planning October can't see that Pat Quinn (incoming Nov 2) is on conference Sep 14–20, because Pat isn't on CRS yet. | Service Chief, Breast Attending | M | Couples to #12 — query for the cohort, not just current occupants |
| 14 | **Coming Next inconsistencies.** (a) Hides PGY tabs with no data — breaks parallelism with Current. (b) Missing the Vacation column that Current has. | Post-call, Service Chief | XS | `app/templates/rotation_detail.html`, `get_coming_next_entries` adds vacation lookup |
| 15 | **No forward-vacation panel on rotation page.** Attending's actual question — "anyone on vacation in the next 2 weeks?" — requires reading every row. A small summary block ("Upcoming vacations: 2 in the next 14 days") would land. | Breast Attending | S | New panel in `rotation_detail.html` |

---

## Tier 5 — Vacation checker UX

| # | Issue | Personas | Effort | Where |
|---|---|---|---|---|
| 16 | **Annual Allowance message is opaque.** "20 already used" with no breakdown. The persona has no way to verify the count is right (and in the categorical PGY-1/2 case, it's wrong — see #2). Add `details:` listing contributing vacation entries. | Vacation Planner | XS | `app/vacation_checker.py:check_annual_allowance` (already supports `details`) |
| 17 | **Call Pool conflict shows duplicate rows per shared pool.** Reads as "6 conflicts" when it's 2 residents. Also surfaces pools the requesting resident isn't in (technically correct but the wording "in the same call pool" is misleading). | Vacation Planner | S | `check_call_pool_conflict` — group by resident, list pools as sub-bullets; reword |
| 18 | **Block-length and start-day errors don't suggest a fix.** "Must be exactly 7 days, but requested 5 days." User has to figure out it should be Mon-Sun or Sat-Fri. Suggest the nearest valid windows. | Vacation Planner | S | `app/vacation_checker.py` |
| 19 | **No "next eligible window" finder.** Users iterate by guess-and-check. A pre-flight scanner would change the experience. | Vacation Planner | M | New helper in `vacation_checker.py` + template section |
| 20 | **Card visibility is subtle.** `border-success` / `border-danger` is easy to miss on a long results page. Sort failures to the top, or use a more prominent indicator. | Vacation Planner | XS | `vacation_checker.html` |

---

## Tier 6 — Navigation polish

| # | Issue | Personas | Effort | Where |
|---|---|---|---|---|
| 21 | **Rotation cells aren't links.** A resident on her detail page can't tap "Surgical ICU" to jump to that rotation page. Same for "By Date" → rotation. | Visiting, Post-call | XS | `prepare_table()` wraps rotation in `<a href="/rotation/{name}/?date={start}">` |
| 22 | **No deep-link from rotation/resident page → vacation checker.** A chief noticing a vacation row has no quick way to "check vacation here for someone else." | Service Chief, Vacation Planner | XS | Row-level link in `rotation_detail.html` |
| 23 | **Resident detail H1 lacks identity context.** "Schedule for Resident: Brooke" — no PGY, no program. For off-service rotators with last-name-only IDs, this is a real anonymity issue. | Visiting | XS | `resident.html` |
| 24 | **No "where am I" cue on by-date page.** Default tab on landing isn't always the persona's PGY. Auto-tab to recently-viewed-resident's PGY would help. | Visiting | S | Small JS in `schedule_table.html` |

---

## Tier 7 — Larger features (worth scoping, not necessarily next)

| # | Issue | Personas | Effort | Where |
|---|---|---|---|---|
| 25 | **Service group abstraction in the rotation view.** A Surgical Oncology chief should be able to see HPB + Mel-Sarc + Breast + Endocrine on one page. East services similarly. The vacation checker already has `SERVICE_GROUPS`; reuse. | Breast Attending, Service Chief | M-L | New `/service/<group>/` route, reuses `SERVICE_GROUPS` from `vacation_checker.py:14` |
| 26 | **"First day briefing" view for short-block visitors.** Single-page hub: dates + co-residents + rotation overview + (eventually) attending + call schedule. | Visiting | L | New route `/block/?resident_id=N` |
| 27 | **Quick-stats summary on rotation page.** "Next 30 days: 3 PGY-1 transitions, 1 PGY-3 transition, 5 vacation weeks." | Service Chief | S | `app/app.py` + template |
| 28 | **Print / CSV / copy-as-table.** Chiefs want to share rosters; visitors want to confirm with home program. | Service Chief, Visiting | M | New endpoint + small template |
| 29 | **Friendly URL slugs for resident pages.** `?id=N` is opaque and resilient to drop-and-recreate would help shared links survive parser re-runs. | Visiting | M | `Resident` model + route changes |

---

## Tier 8 — Cosmetic

| # | Issue | Effort | Where |
|---|---|---|---|
| 30 | **`/` empty-state copy is dismissive** ("hang tight, David will eventually get around to updating it"). At minimum should say *what* dates have data. | XS | `home.html` |
| 31 | **No favicon** (404 on `/favicon.ico`). | XS | `static/` |
| 32 | **Date picker has no min/max** — can spin to 1995 or 2099 and get nothing. | XS | `date_picker.html` |
| 33 | **Footer self-deprecation looks especially bad on empty/no-data pages.** Reasonable in general; consider hiding or muting when results are sparse. | XS | `base.html` |
| 34 | **Inconsistent name format in picker** — most "First Last", some last-name-only, some with `(Doctors Hospital)`. Normalize at parse/display. | S | `parse_schedule.py` + display |
| 35 | **Naming collisions in rotation picker** (Endocrine vs. Breast and Endocrine; Outpatient vs. Outpatient Surgical Oncology). Once #1 is fixed, these are still confusing — group/disambiguate. | S | `rotation_picker.html` |
| 36 | **Mixed elective sub-types in rotation picker** (Cardiac, Gyn, IR, MIS, OB, Ortho, Plastics, Rural, Hernia in the same flat list as real services). Either group under "Electives" optgroup or filter out (since you can't actually be assigned to "Gyn"). | S | `rotation_picker.html` + use `is_elective` from data |

---

## Suggested first-pass batch

If we want a tight, high-value batch that fixes the bugs and removes the worst friction without taking on the larger features:

**Batch A — bugs (~half a day):**
- #1 prefix-match
- #4 vacation checker input validation
- #5 422 friendly error
- #3 dedup vacation rows + DB cleanup
- #8 Tom Select optgroup config

**Batch B — disambiguation (~half a day):**
- #9 year in date columns
- #10 off-service program label in picker + tables
- #14 Coming Next: always show PGY tabs + add Vacation column

**Batch C — vacation logic correctness (1 day):**
- #2 categorical PGY-1/2 exemption (parser emits Vacation rows OR detect via gap)
- #16 Annual Allowance breakdown
- #17 Call Pool conflict grouping

**Batch D — discoverability (1 day):**
- #6 `/` falls through to next available date
- #7 Date input on rotation page
- #21 Rotation cells link to rotation page

After Batch A–D, the *remaining* high-value work is the planning/forward-visibility features (Tier 4) and the service-group abstraction (#25). Those are M-L sized and warrant a design decision before coding (especially #25, which touches both the rotation viewer and the vacation checker's `SERVICE_GROUPS`).
