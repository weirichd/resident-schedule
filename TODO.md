# TODO

## 1. Rotation Detail Page

Add a bookmarkable page for each rotation showing today's schedule and upcoming assignments.

- **Routes:**
  - `/rotation/<name>/` — today's residents on that rotation + "coming next" section
  - `/rotation/<name>/<date>` — residents on that rotation for a specific date
- **Scope:** Minor feature. Mostly new route + template work in `app/app.py`.

---

## 2. Vacation Validity Checker

A web form where residents can check whether a proposed vacation is allowed under program rules. Deterministic Python logic — no LLM needed.

- **Input:** Resident name, proposed vacation start/end dates
- **Output:** Approved/denied with specific rule citations

### Rules to implement (from `vacation_rules.md`):

- **Annual allowance:** 3 weeks vacation (15 weekdays) + 1 flexible week (5 weekdays) per academic year
- **Blackout periods:** No vacation during Block 1 (July), Block 7, or Block 13 (June)
- **Same-service conflict:** No two residents absent from the same service simultaneously. Grouped services count as one:
  - Surgical Oncology: HPB, Melanoma/Sarcoma, Breast, Endocrine
  - East Services: East General Surgery, East ACS, East Vascular
- **Same-call-pool conflict:** No two residents absent from the same call pool simultaneously. Call pools:
  - UH Senior: CRS, HPB, Breast/Endo, Mel/Sarc, ACS, ZE, Hernia/East, Outpatient
  - UH PGY3: ZE, ACS, Colorectal, SICU, Doctors HPB
  - PGY2: Burn, Breast, Outpatient SONC, Vascular, Thoracic, Endoscopy
  - Intern Day: ACS, ZE, Colorectal, East General Surgery, East ACS, East Vascular, Endoscopy, Hernia/East
- **Back-to-back restriction:** No consecutive vacation weeks unless on different services (or chief year final 2 weeks, or special approval)
- **Same-service repeat:** Two vacation weeks cannot be from the same service/block unless separated by 4+ clinical weeks
- **No-vacation rotations:** Night float, Intern Simulation
- **Outside rotators:** No vacation during 1-month transplant block
- **Exempt:** PGY-1 and PGY-2 categorical residents on the vacation block schedule are exempt (coverage is built in)

### Implementation:

- New route: `/vacation_checker/` (form) and `/vacation_check/` (result)
- Query the `schedule` and `vacation` tables to determine what service the resident is on and who else is on the same service/call pool
- Return pass/fail with specific rule violations listed

---

## 3. Parser: Resume Interrupted Conversations

Allow resuming a parse session that was stopped (e.g., Claude asked a question the user couldn't answer immediately).

- Add `--answers <file.md>` CLI arg to `parse_schedule.py`
- The answers file contains responses to questions Claude asked in a previous run
- Enables coming back later with answers without re-running the entire parse from scratch

---

## 4. Unique Resident IDs and Name Flags

Residents should get a unique ID in the DB so that generic names (e.g., "Prelim", "Vascular", "PLASTICS") can be distinguished behind the scenes.

- Add `is_prelim` flag to `resident` table
- Add `is_name` flag to `resident` table (set `FALSE` for generic/placeholder residents like "Vascular" or "PLASTICS")
- Allows multiple residents named "Prelim" to each have their own schedule entries

---

## 5. Parser Improvements (lower priority)

Issues noticed during initial parse that could be addressed in future iterations:

- Handle group/visiting rows (Doctors x4, Anesthesia x22, etc.) — currently skipped
- Handle PGY 4-7 annotation rows if program director wants them
- Add "Thoracic" to valid rotations list (currently unmapped for non-CT residents)
- Clean up name inconsistencies (e.g., "Patel, Sohil" vs last-name-only format)
- Vacation count seems low — verify all PGY-2 vacation blocks were captured
- Consider adding `max_tokens` increase or multi-call strategy for larger schedules
