# Findings — Post-Call Resident (mobile, 390×844)

**Run date:** 2026-05-12
**Persona:** PGY-3 just off a 24h shift. Knows the app, wants the answer fast.
**Goal:** "Who's covering ACS tomorrow? I need to hand off a patient."
**Environment:** Local dev server, mobile viewport.

> Note: today (2026-05-12) is between academic years and `/` shows no data — that blocker is already captured in the new-intern findings. For this run the persona pivots to looking ahead into the next academic year so we can actually exercise the rotation flow.

---

## Journey log

### 1. Landed on `/` → "no data found"

Same dead end as the intern. The post-call resident shrugs and taps the hamburger.

### 2. Opened nav → tapped "By Rotation"

Good: a dedicated rotation entry point exists, no need to first pick a date.

### 3. Rotation picker

- 32 rotations listed alphabetically, Tom Select dropdown with type-to-search.
- Picking "Acute Care Surgery" works — single click after typing "ac".
- **Naming oddities the post-call resident notices instantly:**
  - "Endocrine" *and* "Breast and Endocrine" as separate entries — which is the elective and which is the service?
  - "Outpatient" *and* "Outpatient Surgical Oncology" — same question.
  - "Mount Carmel East" *and* "East General Surgery" — and there is no "East ACS" entry, even though East ACS is a known service per the call-pool rules. Some East work hides under a different rotation name.
  - Elective sub-types (Cardiac, Gyn, IR, MIS, OB, Ortho, Plastics, Rural, Hernia) appear in the same flat list as the core services. The picker doesn't distinguish "elective sub-type" from "real rotation."

### 4. Rotation page `/rotation/Acute Care Surgery/`

This page is the best-designed page in the app. Structure is:
- H1: "Acute Care Surgery" with subtitle "May 12, 2026" (today)
- "Include visiting residents" checkbox
- **Section 1: "Current"** — who is on the rotation right now (PGY tabs)
- **Section 2: "Coming Next"** — next assignment per PGY (PGY tabs)
- Table columns: Resident Name / Rotation / Starting / Until / **Vacation / Conference**

What works well:
- The "Current" + "Coming Next" pair is exactly what a post-call resident wants — *who's on now, who's next*.
- Vacation column on the same table is great: lets you see the handoff *and* its vacation status in one glance.
- PGY tabs let you ignore PGYs you don't care about.

What doesn't:

**No date selector on the page.**
The persona's actual question is *tomorrow*, not *today*. There is no UI affordance to change the date. The endpoint *does* honor a `?date=YYYY-MM-DD` query string (verified: `/rotation/Acute%20Care%20Surgery/?date=2026-07-15` works), but only a power user who reads the source would know that. For everyone else, the rotation view is locked to today, and "tomorrow" requires going to date_picker → date → and there's no rotation filter from there.

**"Current" section silently empty on out-of-data dates.**
At today's date (no data loaded), "Current" reads "No residents are currently assigned to this rotation on this date." The visiting checkbox is still shown, the PGY tabs are still rendered with zero rows. A post-call resident who hits this page on an empty day can't tell whether the rotation legitimately has no one or whether the data is just missing.

**"Coming Next" hides PGY tabs with no data.**
On `?date=2026-07-15` for ACS: Current section shows all 5 PGY tabs (with 0 rows each, since 7/15 is in the data but ACS happens to be in transition); Coming Next shows only PGY 1, PGY 2, PGY 5 — silently dropping PGY 3 and PGY 4. Inconsistent with the Current section, and a post-call resident expecting to see a PGY 3 listed but seeing no tab at all may assume "no PGY 3 coming" rather than "I missed it." Probably a real gap: there may be no PGY 3 rotation entry starting in the near future, but the UI should still show the empty tab.

**`include_visiting` toggle on a rotation page is ambiguous.**
A "visiting" resident from a different program (Podiatry, Neurosurgery, Ortho) absolutely shows up *on* the ACS rotation — that's the whole point of off-service rotators. When I toggle "include visiting residents," do those off-service people disappear too? The label conflates "visiting from outside institution" with "visiting from another department," and the post-call resident genuinely doesn't know which is meant.

**Off-service rotator label is small and unlabeled.**
When Joseph Dunnan (Podiatry) appears on ACS, his program shows as small text under his name (`Joseph Dunnan` with `Podiatry` below in a `<generic>` element). No label says "this person's home program is Podiatry." For a post-call resident handing off a patient, knowing whether the receiving resident is a Podiatry rotator vs a categorical GS resident matters a lot.

### 5. Tried the "Buy me a coffee" footer (curiosity, not the goal)

Renders fine. Reasonable in the footer.

---

## Issues, by severity

### 🔴 Blockers for the persona

1. **No way to pick a different date from the rotation view.** Forces the persona back through the nav and there's no combined date+rotation flow from the date picker either. The whole point of "Who's on ACS tomorrow" is unanswerable without typing a URL by hand.
   - Fix idea: add a date input to the rotation page (same input as date_picker), defaulting to today; on submit reload with `?date=`. Cheap.

### 🟠 Confusing for the persona

2. **"Coming Next" silently drops PGY tabs with no data**, breaking parallelism with the "Current" section. Pick one behavior and apply consistently — preferably "always show the tab, indicate empty" so the page structure doesn't shift.

3. **`include_visiting` semantics are ambiguous on the rotation page.** Does it filter visiting *institutions* (Doctors Hospital), visiting *programs* (Podiatry/Neuro/Ortho/Anesthesia rotating in), or both? The label doesn't say. Rename to "Include off-service rotators" if that's what it does, or split into two filters.

4. **Off-service rotator's home program is not labeled.** A reader sees "Joseph Dunnan Podiatry" and has to infer that "Podiatry" is the home program. Either add a column ("Home Program") or label the sub-text.

5. **Mixed elective sub-types in rotation picker.** Cardiac/Gyn/IR/MIS/OB/Ortho/Plastics/Rural/Hernia appear next to real rotations. Either group them under an "Electives" optgroup or filter them out (since you can't actually *be on* the "Gyn" rotation — it's a sub-type of an elective slot).

6. **Naming collisions in the picker** (Endocrine vs. Breast and Endocrine; Outpatient vs. Outpatient Surgical Oncology). Most are legitimate distinct services but the picker offers no help disambiguating them.

### 🟡 Polish

7. **No year in the Starting/Until columns.** Same issue as the intern persona — "July 01" / "July 12" without "2026". On a "next-rotation" page this is even more confusing because the user is intentionally looking forward.

8. **No "next rotation per resident" link** from the Current rows. Post-call resident wants to know what the current ACS senior rotates to next — would have to click through to that resident's full schedule.

9. **No deep link from "By Date" view to a specific rotation on that date.** If you start at the date picker, you have to drill in by resident, not by rotation.

---

## Suggested fixes (rough ranking by impact)

| # | Fix | Files |
|---|---|---|
| 1 | Add a date input to the rotation view; honor existing `?date=` server-side param via UI | `app/templates/rotation.html`, no app.py change needed |
| 2 | Always show all PGY tabs on "Coming Next", indicate empty inside the tab | `app/templates/rotation.html` |
| 3 | Disambiguate the "Include visiting" toggle (rename, split, or scope) | `app/app.py`, templates, `Resident.is_visiting` semantics |
| 4 | Add an explicit column or pill for off-service rotators' home program | `app/app.py` `prepare_table()` + template |
| 5 | Group rotation picker by "Service" vs. "Elective sub-type" | resident table + parser already has `is_elective` |
| 6 | Add year to schedule date columns (shared with intern findings) | `prepare_table()` |
| 7 | Cross-link from Current rows to the resident's next assignment | template + small query helper |
