# Findings — Visiting Resident (mobile, 390×844)

**Run date:** 2026-05-12
**Persona:** Anesthesia PGY-2 resident on a 1-month surgery elective. The persona for this run is "Brooke" (id 54), Anesthesia PGY-2, scheduled for a single Surgical ICU block 2027-03-01 → 2027-03-31.
**Goal:** "Show me just *my* schedule and who I'll be working with."
**Environment:** Local dev server, mobile viewport.

---

## Journey log

### 1. Looked for myself in `By Resident`

The persona types "Brooke" expecting "Brooke <Last>" or "Brooke (Anesthesia)". What she sees:
- A single dropdown option labeled simply **"Brooke"**. No first name, no department, no PGY.
- For comparison: **Doctors Hospital residents are labeled** with `(Doctors Hospital)` in parentheses. Anesthesia, Urology, Plastics, Orthopedics, Cardiothoracic Surgery, OB rotators get **no label at all** — just a bare last name.

She has no way to verify "Brooke" is her, vs. some categorical resident also named Brooke (or a different Anesthesia resident). She picks it because it's the only Brooke, but the experience is "I hope this is me."

Ranking: **the picker treats institutional visitors as first-class but treats inside-OSU off-service rotators as nameless.** The persona reasonably calls herself a "visiting resident" but the system's `is_visiting` flag means specifically "from another institution." Her presence in the data is implicitly second-class.

### 2. Resident detail page `/resident/?id=54`

What she sees:
- H1: **"Schedule for Resident: Brooke"** — last name only, no first name, no "PGY-2", no "Anesthesia."
- A single-row table: `Brooke / Anesthesia` | `Surgical ICU` | `March 01` | `March 31`.
- The Anesthesia label appears as small sub-text under "Brooke" in the cell. Not labeled — the persona has to infer "Anesthesia" means "her home program."
- **No year** on the dates. She's looking at this in May 2026 for a March 2027 elective. Is this March *2026* (passed)? March *2027*? She can't tell.
- An `Include visiting residents` checkbox is rendered above the single row. Toggling it does nothing (single resident; nothing to filter). Same finding as the new-intern.

### 3. "Who will I be working with?" — no link from her row

Her real Q is "who else is on SICU March 1–31?" The Surgical ICU cell on her detail page is **plain text** — not a link. She has to:
- Manually navigate to By Rotation
- Find Surgical ICU in the (ungrouped) picker of 32 rotation entries
- Pick a date during her block via URL hand-typing (no date input on the rotation page; finding from earlier personas)

That is 5+ taps from her own page to find the team she'll be working with. A link in the Rotation cell would collapse this to one tap.

### 4. SICU rotation page during her block

`/rotation/Surgical ICU/?date=2027-03-15` — once she gets there, this view is decent:
- PGY 1 / PGY 2 / PGY 3 tabs in Current.
- She's listed in the **PGY 2** tab as `Brooke / Anesthesia` along with the other Anesthesia rotators on the same block: Brown, Churma. And one categorical PGY-2: Olivia Duru.
- Her cell again uses the small unlabeled sub-text for "Anesthesia" — but at least she's grouped with people doing the same thing she is.

What she still doesn't see:
- Which of the 4 PGY-2s is the *team* she'll round with (vs. independent assignments).
- Who the SICU attending is. (Not in the data model.)
- The call schedule for the month.
- What "PGY 2" means for her — Anesthesia PGY-2 might rotate alongside surgery PGY-1 interns who outrank her on the SICU floor in practice.

### 5. `Include visiting residents` toggle — semantic mismatch for the persona

Brooke's `is_visiting` is `0`. So the toggle does NOT filter her — confirmed by visiting `/rotation/Surgical ICU/?date=2027-03-15&include_visiting=false`: she's still in the table.

Mental model gap:
- The persona considers herself visiting (she's not a categorical surgery resident).
- The system reserves "visiting" for `Doctors Hospital` residents (an outside institution that shares the surgery training program).
- Off-service rotators from another OSU department are *neither categorical nor visiting* — they don't fit either bucket, but appear with no marker.

The toggle label is ambiguous to the persona. From her POV, "include visiting" should include her too. Or there should be a separate "include off-service rotators" toggle.

### 6. By-date page `/date/?date=2027-03-15` — actually works

She IS listed in the PGY 2 tab on the by-date page. Other Anesthesia / Plastics / Urology / Orthopedics rotators show up too. (Initially looked like a bug because a quick `innerText.includes('Brooke')` returned false — but Bootstrap's hidden tab content is excluded from `innerText`. She's there, just in an inactive tab. Still: the default tab on landing isn't always the persona's PGY, and there's no signal "your match is in PGY 2.")

### 7. No "first day briefing" affordance for someone with a single block

The persona's day-zero question is one-stop:
- Where do I show up Monday morning?
- Who else is on with me?
- Who's in charge?
- What's the call schedule?
- What expectations are different from my home program?

The site can answer #1 and #2 once she's navigated to the rotation page during her block. #3, #4, #5 are not in the data model. There is no opinionated "your block at a glance" view.

### 8. Naming inconsistency hits the persona harder than categoricals

Among the 153 picker options, Anesthesia PGY-1s are listed *only by last name* (e.g., Becker, Cahill, Cestti, Klever, Larsen). Anesthesia PGY-2s the same (Brooke, Brown, Churma, Knorz, etc.). Categorical surgery residents have first names. Doctors Hospital residents have first names *plus* the institutional label. So the off-service rotators are uniquely under-labeled.

For the visiting Brooke persona, "Brooke" alone is anonymous — and the dropdown sorts the "Brooke" entry into the alphabetical run of the PGY-2 group, so she has no contextual neighbors to confirm she picked the right one.

---

## Issues, by severity

### 🔴 Blockers for the persona

1. **Off-service rotators identified by last name only in the picker.** "Brooke" with no first name and no `Anesthesia` label leaves the persona unsure she picked herself. Categorical surgery residents have first+last; institutional visitors have first+last+`(Institution)`; off-service rotators get neither.
   - Fix: either (a) capture first names in the parser for off-service residents (the source spreadsheet may carry only last names — verify), or (b) always append the program label, e.g. `Brooke (Anesthesia)`, when the program isn't General Surgery.

2. **No way to navigate from a resident's rotation cell into that rotation's page.** The persona is one tap away from "who am I working with" if the Rotation cell were a link.
   - Fix: wrap rotation names in `<a href="/rotation/{name}/?date={start_date}">` in `prepare_table()`.

### 🟠 Confusing for the persona

3. **`include_visiting` semantics don't match the persona's mental model.** The toggle filters institutional visitors only — off-service department rotators are unaffected. The persona considers herself "visiting." Either:
   - Rename the toggle to **"Include outside-institution residents"** (true to current behavior), and add a separate **"Include off-service rotators"** toggle for the surgery-only view, OR
   - Combine both into a single "Include non-categorical residents" toggle.

4. **Resident detail H1 lacks identity context.** "Schedule for Resident: Brooke" — should be `Brooke (Anesthesia, PGY-2)` so the persona instantly verifies she's on her own page. Same intent applies to Doctors Hospital residents and categoricals.

5. **No year on date columns in the detail or rotation pages.** A March 2027 elective viewed in May 2026 is genuinely ambiguous. (Same finding from every prior persona, but it's *more* acute for someone whose entire visit is a single block 9 months in the future.)

6. **`Include visiting residents` checkbox shown on single-resident page.** Already noted in the intern findings — it does nothing useful here. Hide it on `/resident/`.

7. **No "where am I in this list" cue on the by-date page.** Brooke landing on the by-date page during her block has to know to click PGY 2; PGY 1 is the default. A "your match is in PGY 2" or auto-tabbing if there's a recently-viewed resident match would help.

### 🟡 Polish

8. **No opinionated "first day briefing" view.** A small-block visitor wants a single page: their dates, their co-residents, the rotation overview. Today they have to navigate by hand.

9. **The "Anesthesia" sub-text under names is unlabeled.** Add `Home program: Anesthesia` either as a tooltip, an inline pill, or a column.

10. **Visiting / off-service residents have no destination URL beyond `/resident/?id=N`.** A shareable link uses an opaque numeric id. A `?slug=brooke-anesthesia` would be friendlier (and survive id reshuffles when the parser drops-and-recreates the DB).

11. **No print/share affordance** — a visitor wanting to confirm her elective dates with her home program has to screenshot.

---

## Suggested fixes (rough ranking by impact)

| # | Fix | Files |
|---|---|---|
| 1 | Always show home program for off-service residents in the picker (`Brooke (Anesthesia)`) | `app/app.py:_pgy_grouped_residents` (or similar), templates |
| 2 | Make rotation names linkable from resident detail and date views | `app/app.py:prepare_table()`, templates |
| 3 | Resident detail H1 includes program + PGY level | `app/templates/resident.html` (or wherever the H1 lives) |
| 4 | Add year to all schedule date columns (shared finding across all 6 personas) | `prepare_table()` |
| 5 | Disambiguate `include_visiting`: rename + add separate `include_off_service` filter | `app/app.py`, templates, Resident model already has `program` |
| 6 | Hide `include_visiting` checkbox on single-resident pages | `app/templates/resident.html` |
| 7 | Auto-tab to the PGY containing a recently-viewed resident on by-date views | small JS in `schedule_table.html` |
| 8 | Add a "block briefing" view for residents with very short rotations: dates + co-residents + rotation overview on one screen | new route `/block/?resident_id=N`, template |
| 9 | Friendly URL slugs for resident pages (resilient to drop-and-recreate) | `Resident` model + route changes |
