# Findings — Vacation Planner (desktop, 1440×900)

**Run date:** 2026-05-12
**Persona:** PGY-2 categorical General Surgery resident planning a wedding. Has never used the vacation checker before.
**Goal:** "I want Aug 10–14, 2026 off for my wedding. Will it conflict? Am I on a no-vacation rotation?"
**Environment:** Local dev server, desktop viewport. Submitted requests for Sohil Patel (PGY-2, id 37).

---

## Journey log

### 1. Landed on `/vacation_checker/`

Form is small and clean: Resident dropdown / Start Date / End Date / Check button. Tom Select dropdown for the resident.

**Same Tom Select optgroup bug as the resident picker.** The HTML has correct `<optgroup label="PGY 1">…</optgroup>` markers but the renderer config is missing `optgroupField`. PGY group headers don't render — the resident sees a flat alphabetical-ish list of 153 names with multiple "A→Z" runs and no PGY labels. Same fix as the new-intern finding.

### 2. First attempt: Aug 10 (Mon) → Aug 14 (Fri), my wedding week

What the persona sees:

| Rule | Result | Message |
|---|---|---|
| Block Length (7 days) | ✗ | Vacation must be exactly 7 days, but requested 5 days. |
| Start Day (Mon or Sat) | ✓ | — |
| Blackout Period | ✓ | — |
| No-Vacation Rotation | ✓ | — |
| Annual Allowance (20 weekdays) | ✗ | Would use 25 of 20 weekdays (20 already used + 5 requested). |
| Same-Service Conflict | ✗ | Shruthi Srinivas on Acute Care Surgery is also on vacation |
| Call Pool Conflict | ✗ | Shruthi Srinivas (UH PGY3 / UH Senior / Intern Day) + Surina Patel (same three) |
| Back-to-Back / Same-Service Repeat / Transplant Block | ✓ | — |

The persona's reaction: "I have *zero* vacation logged in this system. How am I already at 20/20?"

### 3. Investigated "20 already used"

Sohil Patel is a categorical PGY-2 with a 4-week gap in his schedule from 2027-02-08 → 2027-03-07. That gap is the **built-in vacation block** for categorical PGY-1/2 residents. The vacation_checker counts those weekdays toward the annual allowance, but **doesn't surface why** — there's no breakdown ("Block: Feb 8 – Mar 7 = 20 wkdays"). The persona has no idea the system has counted their built-in block as 20/20.

This is **silently wrong in the resident's favor on PGY-1/2**: the built-in block is supposed to *exempt* the resident from these restrictions per the policy ("Residents on the vacation block schedule (categorical general surgery PGY-1 and PGY-2) are exempt from these restrictions, as coverage for their absences is built into the schedule"). The exemption logic exists at `app/vacation_checker.py:611-637`, but it requires a schedule entry where `rotation == "Vacation"` overlapping the requested dates.

**Database check: there are zero `Vacation` rotation entries in the DB.** The parser leaves a gap between assignments rather than emitting a `Vacation` row, so the exemption can *never* fire. Effect:
- A categorical PGY-2 trying to take *additional* vacation outside their block (the wedding scenario) gets dinged on Annual Allowance because the block weekdays are counted but never excluded.
- A categorical PGY-2 trying to take vacation *during* the block (which the policy explicitly exempts) would also fail every rule, because the exemption can't trigger.
- Net: the exemption code path is dead. A straightforward intent in the policy doesn't translate to behavior.

### 4. Second attempt: Aug 10 (Mon) → Aug 16 (Sun) — fix the block-length error

| Rule | Result |
|---|---|
| Block Length | ✓ Vacation is exactly 7 days. |
| Start Day | ✓ Vacation starts on Monday (Mon-Sun). |
| All others same as before | identical |

The block-length error went away. But the *underlying* vacation week the persona cared about is unchanged; they just learned that the system requires Sat-Fri or Mon-Sun blocks. The error message at step 2 told them *what* was wrong but not *what to try next*.

### 5. Call-pool conflict noise

Shruthi Srinivas appears in the conflict list **3 separate times** (one row per pool: UH PGY3, UH Senior, Intern Day). Same for Surina Patel. From the persona's point of view that reads as "wow, six different conflicts" — but it's really two people, listed once per pool overlap.

Worse: the persona is a **PGY-2**. The PGY-2 Call Pool is "Burn, Breast, Outpatient SONC, Vascular, Thoracic, Endoscopy" — they're not in the UH Senior or UH PGY3 pools at all on Aug 10. But the system reports these as conflicts because *the other residents* are in those pools; the rule fires whenever any pool both residents share would overlap. Sohil happens to be on Acute Care Surgery on Aug 10 (which is in UH PGY3, UH Senior, *and* Intern Day pools simultaneously).

Whether this is a real coverage problem is a clinical question, but the *display* gives a PGY-2 persona an answer that looks unrelated to "PGY-2 Call Pool" — the pool name they'd recognize.

### 6. Third attempt: requesting vacation during Night Float — confirms blackout + no-vacation logic works

For 2027-06-07 → 2027-06-13 (Sohil is on Night Float, falls in June blackout):

- ✗ Blackout Period: Blackout: June 1 - June 30
- ✗ No-Vacation Rotation: On Night Float during requested dates
- ✗ Annual Allowance: same 20/20 issue as before

Both blackout and no-vacation rules cleanly fire. Good. (Annual Allowance still erroneously failing.)

### 7. Bad input handling

- **`?resident_id=999` (nonexistent ID):** form re-renders silently with no error and no result. The persona who shared a stale link or fat-fingered an ID has no idea anything was wrong.
- **End date before start date** (`?start_date=2026-08-16&end_date=2026-08-10`): no validation. The page renders the result anyway:
  - Heading: "Aug 16, 2026 to Aug 10, 2026 (0 weekdays)"
  - Block Length rule: "Vacation must be exactly 7 days, but requested **-5** days."
  - Annual Allowance: "Would use 20 of 20 weekdays (20 used + 0 requested, 0 remaining)."
  This is comical — the rules engine should reject inverted ranges before evaluation.
- The HTML date inputs have **no min/max attribute**. A user can pick 1995-08-10 or 2099-08-10 and run the rules.
- The form has no client-side validation that end ≥ start.

### 8. No "what are my options?" affordance

The persona starts with "what's the closest 7-day Mon-Sun window in August that *would* pass?" The form supports only one specific date pair per submission. They have to guess and re-submit. There's no "show me available windows on this rotation" or "next-eligible-date" suggestion.

### 9. No link from rotation page → vacation checker

A resident already on the rotation page (looking at who's on ACS in August) has no shortcut to "check vacation for this person on this date." They have to re-pick the resident in the vacation checker form.

---

## Issues, by severity

### 🔴 Blocker bugs

1. **Categorical PGY-1/2 vacation block exemption is dead code.** `app/vacation_checker.py:617` looks for `entry["rotation"] == "Vacation"` but the parser never emits a `Vacation` rotation. SQL confirms: 0 rows. The dead code path means *every* categorical PGY-1/PGY-2 hitting the checker is treated as a non-categorical for both the annual-allowance baseline and the during-block exemption.
   - Fix options:
     - Make the parser emit explicit `Vacation` rows for the gap between blocks for categorical PGY-1/2 (and only those).
     - Or change the exemption logic to detect "this resident is categorical PGY-1/2 and has a gap of 20 weekdays in their schedule" without relying on a `Vacation` rotation row.
     - Either way, also subtract the block weekdays from the annual-allowance baseline so additional vacation is correctly allowed/denied.

2. **Annual Allowance message is misleading without a breakdown.** Says "20 already used" with no list of which existing vacation entries contribute. The persona has no way to verify the count is correct (and in this case it's wrong, because of bug #1).
   - Fix: show a `details:` list of the contributing vacation entries (date range + weekdays + type). The `RuleResult` schema already supports `details`.

3. **Invalid `resident_id` silently re-renders empty form.** No 404, no error message — the persona thinks "did I submit something?".
   - Fix: catch the missing-resident case in `vacation_check()` and render an explicit error.

4. **No validation on date range.** End-before-start passes through the form and gets treated as a real request, producing nonsense like "requested -5 days." Also no min/max on the date inputs.
   - Fix: in `vacation_check()`, return an error if `req_end < req_start`. Also add `min`/`max` to the date inputs based on academic-year bounds.

### 🟠 Confusing for the persona

5. **Tom Select optgroup headers don't render** in the vacation checker dropdown either. Same root cause as the resident picker; one-line fix in the script tag at `app/templates/vacation_checker.html:106`.

6. **Block-length error doesn't suggest the fix.** "Must be exactly 7 days, but requested 5 days." The user thought of vacation in weekdays, not Mon-Sun blocks. Suggestion: "Try Aug 8 (Sat) – Aug 14 (Fri) or Aug 10 (Mon) – Aug 16 (Sun)."

7. **Call Pool conflict listing duplicates one resident per shared pool.** Reads as "6 conflicts" when it's 2 residents. Group by resident, list pools as a sub-bullet.

8. **PGY-2 call-pool message references pools the PGY-2 isn't in.** A PGY-2 sees "UH Senior Call Pool" and "UH PGY3 Call Pool" listed as their conflicts. Technically the rule is about *both* residents sharing a pool, but the wording "in the same call pool" makes it sound like PGY-2 is in those pools too. Consider phrasing as "Both residents on rotations in the UH Senior Call Pool" so it's clear it's the rotation overlap, not the resident's primary pool.

9. **No academic-year context on the result.** The result heading says "Aug 10, 2026 to Aug 14, 2026 (5 weekdays)" but doesn't tell the persona which AY the allowance is being computed against. A wedding spanning fiscal-year boundaries would be opaque.

### 🟡 Polish

10. **No "next eligible window" suggestion.** Users will iterate; the form forces guess-and-check. A pre-flight scanner ("next 5 valid 7-day windows starting from your requested date") would change the experience.

11. **No deep-link from rotation/resident pages to "check vacation here."** A reader staring at a resident's August block can't jump straight to "check vacation for this resident on this date" — they have to re-enter the resident.

12. **Card colors are subtle** (`border-success` / `border-danger`). On a quick scan it's hard to spot the failures. Consider a more prominent indicator on the failed-rule cards (red tint, sticky "Why this failed" header, or sort failures to the top).

13. **No printable / shareable summary.** A resident filing a vacation request via email needs a screenshot. A "copy summary to clipboard" or a print-friendly mode would help.

14. **Footer self-deprecation** ("no guarantee… use at your own risk") sits directly under the rule cards. For a tool that's making a yes/no policy determination, this is louder than it should be.

---

## Suggested fixes (rough ranking by impact)

| # | Fix | Files |
|---|---|---|
| 1 | Wire up the categorical PGY-1/2 vacation-block exemption (parser emits `Vacation` rows, OR detect gap heuristically) | `parse_schedule.py`, `app/vacation_checker.py:611-637` |
| 2 | Subtract built-in block weekdays from the Annual Allowance baseline, and surface contributing entries in `details` | `app/vacation_checker.py:check_annual_allowance` |
| 3 | Reject invalid `resident_id` and inverted date ranges with explicit errors | `app/app.py:387` (`vacation_check`) |
| 4 | Fix Tom Select optgroup config (one-line) | `app/templates/vacation_checker.html:106` |
| 5 | Add `min` / `max` date input attributes scoped to current AY | `app/templates/vacation_checker.html:38,43` |
| 6 | Group call-pool conflicts by resident; list pools as sub-bullets | `app/vacation_checker.py:check_call_pool_conflict` |
| 7 | Add a "suggested fix" string to block-length and start-day rule messages | `app/vacation_checker.py` |
| 8 | Add a "next eligible windows" finder that surfaces the closest valid 7-day blocks to the requested date | new helper in `vacation_checker.py` + template section |
| 9 | Deep-link from rotation/resident pages into the vacation checker prefilled | `app/templates/rotation_detail.html`, resident view |
