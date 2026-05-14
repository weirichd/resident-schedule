# Findings — Brand-New Intern (mobile, 390×844)

**Run date:** 2026-05-12
**Persona:** PGY-1 on/before day 1 of residency. No prior knowledge of this site.
**Goal:** "Where am I supposed to be Monday morning?"
**Environment:** Local dev server, iPhone-ish mobile viewport.

---

## Journey log

### 1. Landed on `/`

What the intern saw:
- Heading: "Current Schedule for Today"
- Body: **"No data was found. This is most likely due to the schedule being out of date. If it is still early in the school year, hang tight, David will eventually get around to updating it."**

What the intern thinks: "I just got hired and the site is telling me it's broken." There is no indication of *what* date ranges have data, no link to "view a different date," no acknowledgement that the next academic year starts soon.

The empty state is informal and dismissive — fine for friends/family but actively unhelpful for an intern who needs to do something *now*.

### 2. Opened nav, picked "By Resident"

Five nav items: Today / By Date / By Rotation / By Resident / Vacation Checker. The intern picks "By Resident" hoping to find themselves.

### 3. Resident picker

- One large dropdown with **153 options** and a "Type a name to search…" placeholder.
- The data has `<optgroup>` tags for `PGY 1` / `PGY 2` / `PGY 3` / `PGY 4` / `PGY 5` (PGY 1 alone has 76 entries) **but Tom Select isn't rendering the group headers**. The renderer is defined for `optgroup_header` but the config is missing `optgroupField` / `optgroups`, so groups are silently flattened.
- Name format is inconsistent: most are "First Last", but some are last-name only (Becker, Cahill, Cestti, Klever, Larsen) and some carry a parenthetical institution ("Jacob Spencer (Doctors Hospital)"). An intern who knows themselves as "Mike Smith" won't find themselves if the schedule lists them as "Smith".
- The visible alphabetical run resets multiple times (A–Z, then A–Z again, then A–Z again) because the underlying optgroups are sequential. Without visible group headers this looks like a sorting bug.
- The 76 PGY-1 entries include all the off-service rotators (Neuro, Ortho, Anesthesia, OB, etc.). For a categorical surgery intern, the list is 5× longer than necessary.

### 4. Picked a resident → `/resident/?id=<n>`

- The picker submits via JS: `window.location.href = '/resident/?id=' + value`. Works.
- Headings, layout, and table render OK on mobile.
- Schedule table columns: Resident Name / Rotation / Starting / Until.
- **No year shown** in the Starting/Until columns ("November 01", "November 30"). For an intern looking at this in May, they can't tell whether "November" means 2025 or 2026.
- For off-service rotators (e.g., Alec Jonason, "Neurosurgery"), only one row is shown — the single month they're on surgery. The intern wouldn't know that's *all* the data, vs. a bug.
- **The "Include visiting residents" checkbox is shown on a single-resident page.** This is nonsensical here — you're already viewing one specific person; toggling visiting filters does nothing useful.
- The resident's program (e.g., "Neurosurgery") appears as a small sub-label under their name in the table cell. Not labeled. The intern doesn't know what that text is.

### 5. Tried `/resident/?name=...` directly (typo / curiosity)

- Result: raw JSON 422 error dumped on screen: `{"detail":[{"type":"missing","loc":["query","id"],"msg":"Field required","input":null}]}`.
- This is the FastAPI default 422. Anyone who shares a link with the wrong param or mistypes one gets this. No friendly error page.

### 6. Tried "By Date" with the actual academic-year start (2026-07-01)

- Date input has no min/max and no default value. Mobile users get the native picker but with no hint about what date range has data.
- Picking 2026-07-01 *does* load data (60 rows, tabbed by PGY 1–5). So data is there, just not at "today."

---

## Issues, by severity

### 🔴 Blockers for the persona

1. **`/` shows no data on May 12 (between academic years).** The empty state effectively communicates "this site is broken." For an intern who lands here in May–June (the most likely time for a new hire to discover the site), this is the *first* impression.
   - Fix idea: when "today" has no schedule, automatically show the closest dated schedule with a banner ("Showing 2026-07-01 — the next available date"), or render a date-range hint ("Schedule data available 2026-07-01 to 2027-06-30").

2. **422 JSON dumped on `/resident/?name=...` and similar mistakes.** Easy to share a bad link. No graceful fallback.
   - Fix idea: catch validation errors and render a small error page that points back to the picker.

### 🟠 Confusing for the persona

3. **PGY optgroup headers don't render in the resident picker.** Tom Select needs `optgroupField`, e.g. `optgroupField: 'optgroup'` plus an `optgroups` array, or use `dataAttr` config. The data is correct in the HTML — the widget is just hiding it.

4. **Inconsistent name format in the picker.** Some last-name-only, some first+last, some with parenthetical institution. Search-by-typing partly mitigates this but only if you know which form your name takes.

5. **No year in the resident schedule table.** "November 01" / "November 30" with no year is ambiguous on the cusp of the academic year. Either show "Nov 01, 2026" or group rows by academic year with a header.

6. **"Include visiting residents" checkbox appears on the single-resident page.** It does nothing meaningful on this page and adds confusion.

7. **Off-service rotators are mixed into the PGY-1 group with no distinction.** The picker shows 76 PGY-1 entries; an intern doesn't know which 5–10 are categorical general surgery.

### 🟡 Polish

8. **Empty-state copy on `/` is too informal** ("hang tight, David will eventually get around to updating it"). Friendly but unhelpful — at minimum it should say *what* dates have data and link to them.

9. **No favicon** — 404 on `/favicon.ico` in console. Not user-facing but shows up in error consoles and looks unfinished.

10. **Date picker has no min/max bounds.** Mobile users can spin to 1995 or 2099 and get nothing.

11. **Footer self-deprecation appears on every page** ("Mr. Dr. Huang… no guarantee… use at your own risk"). On a screen with no data, the footer is the loudest thing. Reasonable on a polished page; on the empty-today page it reads as "the site doesn't work."

---

## Suggested fixes (rough ranking by impact)

| # | Fix | Files |
|---|---|---|
| 1 | `/` empty-state: fall through to next available date with a banner, or show data-range hint | `app/app.py`, `app/templates/today.html` (or equivalent) |
| 2 | Catch FastAPI 422 → render a friendly error page that links to pickers | `app/app.py` (`@app.exception_handler(RequestValidationError)`) |
| 3 | Fix Tom Select optgroup rendering | `app/templates/resident_picker.html` (config + maybe template macro) |
| 4 | Add year to schedule table date cells | `app/app.py` `prepare_table()` |
| 5 | Hide "Include visiting" on single-resident pages | `app/templates/resident.html` |
| 6 | Normalize name format at parse/display time (e.g., always "First Last" when first name known) | `parse_schedule.py` + display layer |
| 7 | Distinguish categorical GS from off-service rotators in the picker (separate group / badge) | resident picker + `Resident` model uses `program`, already available |
| 8 | Rewrite `/` empty-state copy and `date_picker` to surface data range | `app/app.py`, templates |
