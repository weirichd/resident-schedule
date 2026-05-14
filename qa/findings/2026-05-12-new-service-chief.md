# Findings — New Service Chief (desktop, 1440×900)

**Run date:** 2026-05-12
**Persona:** Newly appointed Colorectal Surgery service education liaison. Senior resident or attending who needs to think across the next 1–3 months of staffing for their service.
**Goal:** "Show me everyone rotating through CRS for the next 3 months and flag any vacation overlaps."
**Environment:** Local dev server, desktop viewport. Probed dates 2026-09-15, 2026-09-16, 2026-11-15.

---

## Journey log

### 1. Navigated to By Rotation → Colorectal Surgery → `/rotation/Colorectal Surgery/?date=2026-09-15`

The chief's question is about a 3-month window starting now. The page only answers about *one date*. Title reads "September 15, 2026" — singular point in time.

Page structure:
- Current section, PGY 1 / PGY 3 / PGY 5 tabs
- Coming Next section, single PGY tab (PGY 1 only on this date)
- Vacation/Conference column on Current; **no vacation column** on Coming Next.

**For the 3-month picture, the chief has to step the URL date manually** (in 4-week increments) and combine the views in their head. There is no consolidated "next N weeks" view.

### 2. What's actually in the next 3 months (verified via SQL for ground truth)

```
PGY 1: Kartik (Urology), Klever (Anesthesia), Angela Duff, Grant Sajdak (Urology),
       Ted Dimitrov (CT), Becker (Anesthesia), Michelle Garrison, Furrukh (Plastics)
PGY 3: Alex Powell, Michelle Chan
PGY 5: Shruthi Srinivas, Pat Quinn
```

That is 12 resident-block assignments across 3 months. The chief needs to understand:
- 6 of the 8 PGY-1 slots are filled by *off-service rotators* (Urology / Anesthesia / CT / Plastics). Education planning for those is different from for categorical PGY-1s.
- Continuous chief coverage transitions: Shruthi Srinivas → Pat Quinn on Nov 2.
- PGY-3 transitions: Alex Powell → Michelle Chan on Oct 19.
- Vacation overlap on Sep 14–20: 4 different residents off that week (more on this below).

The current rotation page surfaces 3 of these and forces the chief to drill in for the rest.

### 3. Vacation overlap on Sep 14–20 — partly invisible

On the Sep 16 page the chief sees:
- Alex Powell (current PGY-3) row reads `ON VACATION: Sep 14–Sep 20`.

What the chief *doesn't* see, but matters:

| Resident | PGY | Vac dates | Vac type | Rotation that week | Visible on the CRS page? |
|---|---|---|---|---|---|
| Alex Powell | 3 | Sep 14–20 | vacation | Colorectal | ✅ shown |
| Pat Quinn | 5 | Sep 14–20 | conference | not yet on CRS (starts Nov 2) | ❌ |
| Michelle Chan | 3 | Sep 14–20 | vacation | not yet on CRS (starts Oct 19) | ❌ |
| Grant Sajdak | 1 | Sep 14–20 | vacation | not yet on CRS (starts Sep 21) | ❌ |

The chief planning a 3-month forward window cares about the *future* CRS team's leave conflicts too, not just whoever happens to be on the rotation today. Pat Quinn (incoming PGY-5) being out for a conference the same week as Michelle Chan (incoming PGY-3) is a coordination question even though neither is on CRS that week. The page can't surface this without already knowing who'll be on CRS in October–December.

### 4. Coming Next section is too thin

`get_coming_next_entries()` returns *one* row per PGY — the next assignment after the current block. So:
- On the Sep 15 page, Coming Next shows only PGY 1 (Angela Duff and Grant Sajdak starting Sep 21). PGY 3 and PGY 5 tabs are entirely missing — same finding as the post-call resident.
- Even when the chief jumps to the Nov 15 page, Coming Next still only shows the *next* assignment, not the rest of the season.

For chief-level planning, "next" should be "remaining coming up over the next N weeks" — ideally a configurable window.

### 5. Coming Next is missing the Vacation column

Compare table columns:
- Current: Resident Name / Rotation / Starting / Until / **Vacation / Conference**
- Coming Next: Resident Name / Rotation / Starting / Until *(no vacation column)*

The chief would specifically want to see "Pat Quinn starts Nov 2 — and is on conference Sep 14–20" (his pre-CRS vacation/conference might or might not be relevant, but at minimum vacations *during* the upcoming block need to be visible). Right now the page hides them.

### 6. Off-service rotators not distinguished structurally

The PGY 1 tab on the CRS page mixes 8 categorical and off-service rotators. The off-service rotators carry their home-program label as small sub-text under the name (e.g., "Kartik Patel" with "Urology" below in small type). This is the *only* visual differentiation. The chief responsible for *categorical* CRS PGY-1 education needs to:
- Mentally filter for the 2 categorical rows out of 8.
- Realize that "Urology" / "Anesthesia" / "Plastics" / "Cardiothoracic Surgery" sub-text means "off-service" — there's no "off-service" badge.

### 7. `Include visiting residents` checkbox

Same ambiguity flagged in earlier findings. From a chief's standpoint, the question is "show me only my categorical residents" — that filter doesn't exist as a single toggle. (`is_visiting` is for outside-institution rotators like Doctors Hospital; off-service rotators from inside OSU show up regardless.)

### 8. Discovered a **parser bug**: duplicate vacation entries

While verifying the Sep 14–20 conflict, found that Grant Sajdak has *four* vacation rows in the DB:
```
51 | 2026-09-14 | 2026-09-20 | vacation
127| 2026-09-14 | 2026-09-18 | vacation
103| 2027-06-07 | 2027-06-13 | vacation
128| 2027-06-07 | 2027-06-11 | vacation
```
Two pairs of overlapping entries — same start date, end date varying by 2 days. Almost certainly the parser saw the same vacation in two different cell representations (Mon-Fri and Mon-Sun) and inserted both.

Effect:
- Vacation conflict checks may double-count (the call-pool conflict in the Vacation Planner findings already lists each conflicting resident once per overlapping pool, which compounds with this bug if it triggers).
- The CRS page would show Grant Sajdak's vacation cell twice if he were on CRS during one of those windows.
- The Annual Allowance check counts each row independently — Grant's "used" weekdays would be inflated.

### 9. No service-group view

The policy groups Surgical Oncology services (HPB / Melanoma-Sarcoma / Breast / Endocrine) for vacation conflict purposes (`SERVICE_GROUPS` in `app/vacation_checker.py:14`). A SONC chief asking "who's on Surgical Oncology in November?" would have to visit four separate rotation pages and combine in their head. CRS doesn't have a group, but the abstraction is missing in the rotation viewer entirely.

### 10. No print/export

The new chief might want to share an "October roster" with their service. There is no print mode, CSV export, or copy-as-table affordance.

---

## Issues, by severity

### 🔴 Blockers for the persona

1. **No multi-week / multi-month forward view.** The whole reason to give a chief a "by rotation" page is to plan ahead. Single-date snapshots force the chief to scrub the URL by hand and reassemble in their head.
   - Fix: a "next 90 days on CRS" timeline view — one row per resident, blocks colored by PGY, vacations shaded over the block. Even a flat table of all (resident, block-start, block-end, PGY, vacation-in-block) for the next N days would beat what's there.

2. **Future rotators' vacations are completely invisible.** The chief planning Oct/Nov can't see that Pat Quinn (incoming Nov 2) is on conference Sep 14–20 or that Michelle Chan (incoming Oct 19) is on vacation that week — because both are still on a different service then.
   - Fix: as part of the look-ahead view, list all vacations for the *cohort of residents who will be on CRS in window W*, regardless of whether they're on CRS during the vacation.

3. **Parser is creating duplicate vacation rows.** Confirmed for Grant Sajdak — two separate insertions for the same vacation week. Likely affects more residents.
   - Fix: dedup logic in `parse_schedule.py:write_to_db()` (drop rows where `(resident_id, vac_start)` collides with an existing row, or the wider `(resident_id, vac_start, vac_end)` collision), and a one-time DB cleanup query.

### 🟠 Confusing for the persona

4. **Coming Next is "the next single block" per PGY.** The chief has no visibility past one transition. Expand to "all upcoming assignments in the next N days" (configurable, default 90).

5. **Coming Next table is missing the Vacation column.** Inconsistent with Current, and structurally hides the data the chief most needs (incoming residents' vacations in their incoming block).

6. **Coming Next hides PGY tabs with no data.** Already noted by the post-call resident, but it's even worse for a chief — "Coming Next has only a PGY 1 tab" reads as "no PGY 3 or PGY 5 coming next" rather than "no PGY 3 or PGY 5 starting in the very next 4 weeks."

7. **No off-service vs. categorical visual distinction.** Sub-text under the name is the only signal. Add an explicit badge (`OFF-SERVICE`, with home program), and ideally a filter ("show categorical only").

8. **Service group abstraction missing from rotation view.** A SONC chief should be able to land on a single page that shows HPB + Mel-Sarc + Breast + Endocrine together. Reuse `SERVICE_GROUPS` from the vacation checker.

### 🟡 Polish

9. **No date input on the rotation page** (already noted twice in earlier persona runs). For a chief who plans to refresh weekly, no UI affordance to advance the date is a real friction.

10. **No "quick stats" header** — e.g., "Next 30 days: 3 PGY-1 transitions, 1 PGY-3 transition, 5 vacation weeks". Even one line of summary would orient the chief instantly.

11. **No print / CSV / copy-as-table.** The chief who wants to share October roster has nothing to grab.

12. **Year not in date columns.** Same finding as earlier personas — the chief planning across the Dec/Jan boundary doesn't see year transitions.

13. **No deep-link from rotation page → vacation checker prefilled with the resident + the block dates.** The chief noticing Alex Powell on vacation Sep 14–20 has no quick way to "check which other CRS residents could cover that week."

---

## Suggested fixes (rough ranking by impact)

| # | Fix | Files |
|---|---|---|
| 1 | Add a "Look Ahead" view to the rotation page: configurable window (default 90 days), table of all assignments + their vacation overlays, sorted by start date | `app/app.py`, new template section in `rotation_detail.html` |
| 2 | Surface "future rotators' vacations" — for any vacation in the look-ahead window where the resident will be on this rotation at some point in the window, show it | `app/app.py` (extend rotation query) |
| 3 | Dedup vacation rows on parse; investigate the Mon-Fri vs Mon-Sun source pattern | `parse_schedule.py:write_to_db` (around line 604) |
| 4 | Run a DB cleanup query to remove existing duplicate vacation rows | one-off SQL or a small migration script |
| 5 | Add Vacation column to Coming Next table for parity with Current | `app/app.py:get_coming_next_entries`, template |
| 6 | Always render all PGY tabs in Coming Next, even when empty | `app/templates/rotation_detail.html` |
| 7 | Add an off-service badge / column and a "categorical only" filter | `app/app.py` `prepare_table()` + template + Resident model already has `program` |
| 8 | Add an opt-in service-group view (CRS, SONC, East) reusing `SERVICE_GROUPS` | `app/vacation_checker.py:14`, new route `/service/<group>/` |
| 9 | Date input on rotation page (shared with post-call & breast attending findings) | `app/templates/rotation_detail.html` |
| 10 | "Quick stats" summary line at top of rotation page | `app/app.py` (compute), template |
| 11 | Year in date columns (shared with all earlier findings) | `prepare_table()` |
| 12 | Deep-link rows → vacation checker prefilled | row-level link in `rotation_detail.html` |
