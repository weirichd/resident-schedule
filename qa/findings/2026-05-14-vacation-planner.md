# Findings — Vacation Planner (desktop, 1440×900) — Re-run

**Run date:** 2026-05-14
**Persona:** PGY-2 categorical General Surgery resident planning a wedding.
**Goal:** "I want Aug 10–14, 2026 off for my wedding."
**Compares to:** [2026-05-12-vacation-planner.md](2026-05-12-vacation-planner.md) — original 14-issue run.

---

## What changed since the original run

| Original issue | Status |
|---|---|
| 1. Categorical PGY-1/2 vacation block exemption is dead code | ✅ **Fixed** — exemption now fires when request is fully inside an existing 15+ weekday vacation entry; verified via Sohil Patel Feb 8–14 request showing the friendly Exempt alert |
| 2. Annual Allowance message has no breakdown | ✅ **Fixed** — now lists every contributing entry with type, dates, and weekday count ("Vacation: Feb 08–Mar 07, 2027 (20 weekdays)") |
| 3. Invalid `resident_id` silently re-renders | ✅ **Fixed** — returns 404 with form-level error message |
| 4. No validation on date range (end < start) | ✅ **Fixed** — returns 400 with explicit error |
| 5. Tom Select optgroup not rendering | ✅ **Fixed** — PGY 1-5 group headers visible |
| 6. Block-length error doesn't suggest a fix | ❌ **Unfixed** — message still says "must be exactly 7 days, but requested 5 days" without nudging to the right window |
| 7. Call Pool conflict listing duplicates one resident per pool | ✅ **Fixed** — grouped by resident, pools listed inline as "(shared pool: A, B, C)" |
| 8. PGY-2 call-pool message references pools they aren't in | ✅ **Improved** — message reworded to "Another resident's vacation overlaps a shared call pool" instead of "in the same call pool" |
| 9. No academic-year context on result | ❌ **Unfixed** — heading still doesn't say which AY |
| 10. No "next eligible window" suggestion | ❌ **Unfixed** — Tier 5 #19, deferred |
| 11. No deep-link from rotation/resident pages → vacation checker | ❌ **Unfixed** — Tier 6 #22, deferred |
| 12. Card colors subtle | ❌ **Unfixed** — Tier 5 #20, deferred |
| 13. No printable summary | ❌ **Unfixed** |
| 14. Footer self-deprecation under rule cards | ❌ **Unfixed** |

**Persona-experience summary:** the *correctness* problems are gone. The exemption works, the allowance breakdown shows what's contributing, bad inputs land on a recoverable error instead of silently resetting or producing nonsense like "requested -5 days." The remaining gaps are primarily UX polish and the larger "next eligible window" feature.

---

## Journey log

### 1. Tested during-block exemption: Sohil Patel, Feb 8–14, 2027 (inside his Feb 8–Mar 7 block)

Result page:
- Heading: "Sohil Patel (PGY-2) — Feb 08, 2027 to Feb 14, 2027 (5 weekdays)"
- Info banner: **"Exempt: PGY-1/PGY-2 categorical General Surgery residents on the vacation block schedule are exempt from vacation restrictions."**
- No rule cards rendered (because exempt).

This was the original Tier 1 #2 bug. Now works.

### 2. Tested outside-block: Sohil Patel, Aug 10–14, 2026 (the wedding scenario)

| Rule | Result | Message |
|---|---|---|
| Block Length (7 days) | ✗ | Vacation must be exactly 7 days, but requested 5 days. |
| Start Day | ✓ | Monday (Mon-Sun) |
| Blackout Period | ✓ | — |
| No-Vacation Rotation | ✓ | — |
| Annual Allowance (20 weekdays) | ✗ | Would use 25 of 20 weekdays (20 already used + 5 requested). **Vacation: Feb 08–Mar 07, 2027 (20 weekdays)** |
| Same-Service Conflict | ✗ | Shruthi Srinivas on Acute Care Surgery is also on vacation |
| Call Pool Conflict | ✗ | Shruthi Srinivas (shared pool: Intern Day Call Pool, UH PGY3 Call Pool, UH Senior Call Pool); Surina Patel (shared pool: Intern Day Call Pool, UH PGY3 Call Pool, UH Senior Call Pool) |
| Back-to-Back, Same-Service Repeat, Transplant Block | ✓ | — |

Compare to the original run:
- **Annual Allowance now explains itself.** Originally said "20 already used" with no breakdown — now shows the contributing block. The persona instantly understands why the system says they're at 20/20.
- **Call Pool conflicts went from 6 lines to 2.** Originally each conflicting resident was listed once per shared pool (Shruthi×3 + Surina×3). Now grouped: 1 line per resident with the shared pools inline.
- **Block-length error still doesn't suggest a fix.** A persona who chose Mon-Fri thinking in weekdays still has to figure out that the system wants Mon-Sun blocks.

### 3. Bad input handling

- **Invalid `resident_id=999`:** form re-renders with a yellow alert "No resident found with id 999." 404 status.
- **Inverted date range** (`start=2026-08-16&end=2026-08-10`): yellow alert "End date must be on or after start date." 400 status. No "requested -5 days" nonsense.
- **Garbage date** (`start=garbage`): yellow alert "Start and end dates must be valid YYYY-MM-DD dates."
- Date inputs have `min`/`max` attributes scoped to current AY through next AY (2025-07-01 to 2027-06-30 today), so wedding planning a year out works.

### 4. Picker

PGY 1-5 group headers render. Off-service rotators labeled with their program. Same as the resident picker.

---

## Remaining issues (carried over)

### 🟠 Confusing for the persona

1. **Block-length error doesn't suggest the fix.** "Try Aug 8 (Sat) – Aug 14 (Fri) or Aug 10 (Mon) – Aug 16 (Sun)" would be one line of code. (Carryover #6.)

2. **No academic-year context on the result.** Heading just says the date range, not which AY the allowance is being computed against. (Carryover #9.)

### 🟡 Polish

3. **No "next eligible window" finder.** Users still iterate by guess-and-check. (Carryover #10, Tier 5 #19.)

4. **No deep-link from rotation/resident pages → vacation checker.** (Carryover #11, Tier 6 #22.)

5. **Card colors still subtle.** Failures could be visually louder. (Carryover #12, Tier 5 #20.)

6. **No printable / shareable summary.** (Carryover #13.)

7. **Footer self-deprecation under rule cards.** (Carryover #14.)

---

## Issues introduced or noticed for the first time

None. The vacation logic is now actually correct for the categorical case.

---

## Score-card

- **Original blocker bugs (4):** 4 fixed (exemption, allowance breakdown, invalid id, date validation).
- **Original confusing (5):** 4 fixed/improved (Tom Select, call pool grouping, call pool wording, allowance breakdown), 1 unfixed (block-length suggestion).
- **Original polish (5):** 0 fixed; all 5 are deferred Tier 5/6 items.

The vacation checker went from "actively misleading and silently broken" to "correct, with the remaining gaps being incremental polish." The categorical PGY-1/2 confusion (originally the headline issue) is gone.
