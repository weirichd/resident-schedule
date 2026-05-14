# Findings — New Service Chief (desktop, 1440×900) — Re-run

**Run date:** 2026-05-14
**Persona:** Newly appointed Colorectal service education liaison.
**Goal:** "Show me everyone rotating through CRS for the next 3 months and flag any vacation overlaps."
**Compares to:** [2026-05-12-new-service-chief.md](2026-05-12-new-service-chief.md) — original 13-issue run.

---

## What changed since the original run

| Original issue | Status |
|---|---|
| 1. No multi-week / multi-month forward view | ❌ **Unfixed** — Tier 4 #12, deferred. Date input partially helps (chief can step through dates without URL hand-typing). |
| 2. Future rotators' vacations completely invisible | ❌ **Unfixed** — Tier 4 #13, deferred. |
| 3. Parser is creating duplicate vacation rows | ✅ **Fixed** — parser deduplicates on (resident_id, vac_start) keeping longest range. Existing dups cleaned: Grant Sajdak now has 2 entries (was 4); 137 → 127 vacation rows total. |
| 4. Coming Next is "next single block" per PGY | ❌ **Unfixed** — Tier 4 #12 |
| 5. Coming Next missing Vacation column | ✅ **Fixed** — column always present now |
| 6. Coming Next hides PGY tabs with no data | ✅ **Fixed** — tabs padded; missing PGYs render "No PGY X residents in this section." |
| 7. No off-service vs categorical visual distinction | ◐ **Improved** — picker labels off-service rotators with their program; tables already show program inline; no first-class "categorical only" filter |
| 8. Service group abstraction missing from rotation view | ❌ **Unfixed** — Tier 7 #25, deferred |
| 9. No date input on rotation page | ✅ **Fixed** |
| 10. No "quick stats" header | ❌ **Unfixed** — Tier 7 #27 |
| 11. No print/CSV/copy-as-table | ❌ **Unfixed** — Tier 7 #28 |
| 12. Year not in date columns | ✅ **Fixed** |
| 13. No deep-link from rotation row → vacation checker | ❌ **Unfixed** — Tier 6 #22 |

**Persona-experience summary:** the chief's biggest single complaint — "I can't even see all 5 PGYs consistently in Coming Next" — is fixed. The data integrity issue (duplicate vacation rows) is also fixed. But the *real* value the chief was asking for — a multi-month forward view with future rotators' vacations — is the Tier 4 work we explicitly deferred. So the experience is meaningfully better but not transformed.

---

## Journey log

### 1. CRS rotation page on Sep 15, 2026

The chief sees:

**Current section** (PGY 1 / 3 / 5 tabs):
- PGY 1: Kartik Patel (Urology) Aug 24 → Sep 20; Klever (Anesthesia) Sep 01 → Sep 30
- PGY 3: Alex Powell Aug 24 → Oct 18, **ON VACATION: Sep 14, 2026–Sep 20, 2026**
- PGY 5: Shruthi Srinivas Aug 31 → Nov 01

**Coming Next section** (also PGY 1 / 3 / 5 tabs — symmetric with Current):
- PGY 1: Angela Duff and Grant Sajdak (Urology), both Sep 21 → Oct 18
- PGY 3: *empty tab — "No PGY 3 residents in this section."*
- PGY 5: *empty tab*

The off-service rotators (Urology, Anesthesia) are clearly labeled. The chief can see:
- 2 of the 4 current PGY-1 slots are categorical → they're his focus for education
- Alex Powell is on vacation Sep 14–20 (the only week with a vacation overlap visible from this snapshot)

### 2. What the chief still can't see

- Pat Quinn (incoming PGY-5, starts Nov 2) is on conference Sep 14–20 — *not visible* because Pat isn't on CRS until Nov.
- Michelle Chan (incoming PGY-3, starts Oct 19) is on vacation Sep 14–20 — *not visible* for the same reason.
- Grant Sajdak (incoming PGY-1, starts Sep 21) is on vacation Sep 14–20 — *not visible*.

So 3 of the 4 residents off the same week are still hidden from the chief who's planning around CRS staffing. The "next 90 days for this rotation's cohort" view (Tier 4 #12) is the unblocking work.

### 3. Date input

Chief can advance week-by-week using the date input. Better than URL hand-typing, but the chief still has to mentally reassemble the picture across 3-4 separate page loads.

### 4. Parser dup bug

Verified: Grant Sajdak now has 2 vacation entries (was 4 in the original run). The DB has 127 vacation rows total (was 137). The parser change ensures new parses won't reintroduce dups.

---

## Remaining issues (carried over)

### 🔴 Blockers for the persona

1. **No multi-week / multi-month forward view.** Still the headline gap. (Carryover #1, Tier 4 #12.)

2. **Future rotators' vacations are invisible.** (Carryover #2, Tier 4 #13.)

### 🟠 Confusing for the persona

3. **No "categorical only" filter.** (Carryover #7.)

4. **No service-group view.** A SONC chief still has to visit 4 separate pages to see all of HPB/Mel-Sarc/Breast/Endocrine. (Carryover #8, Tier 7 #25.)

### 🟡 Polish

5. **No quick-stats summary.** "Next 30 days: 3 transitions, 5 vacation weeks." (Carryover #10.)

6. **No print/CSV.** (Carryover #11.)

7. **No deep-link to vacation checker** from rotation rows. (Carryover #13, Tier 6 #22.)

---

## Issues introduced or noticed for the first time

None.

---

## Score-card

- **Original blockers (3):** 1 fixed (parser dup), 2 unfixed (forward view, future vacations).
- **Original confusing (4):** 2 fixed (Coming Next vacation column + PGY tabs), 1 improved (off-service distinction), 1 unfixed (service group).
- **Original polish (6):** 2 fixed (year, date input), 4 unfixed.

The chief's *correctness* problem (parser dups) and *consistency* gripes (Coming Next behavior) are resolved. The *transformation* the chief was actually asking for — a real planning view — is the deferred Tier 4 work. Net: **moderate improvement**, with the headline gap intentionally left for a future batch.
