# Findings — Brand-New Intern (mobile, 390×844) — Re-run

**Run date:** 2026-05-14
**Persona:** PGY-1 on/before day 1 of residency. No prior knowledge of this site.
**Goal:** "Where am I supposed to be Monday morning?"
**Compares to:** [2026-05-12-new-intern.md](2026-05-12-new-intern.md) — original 11-issue run.

---

## What changed since the original run

| Original issue | Status |
|---|---|
| 1. `/` empty-state on May 12 between AYs | ✅ **Fixed** — auto-falls through to Jul 01, 2026 with banner |
| 2. 422 JSON dump on `/resident/?name=foo` | ✅ **Fixed** — friendly error page with picker links |
| 3. Tom Select PGY optgroup headers don't render | ✅ **Fixed** — all 5 PGY headers visible |
| 4. Inconsistent name format in picker | ◐ **Improved** — off-service rotators now labeled "(Anesthesia)" / "(Urology)" / "(Neurosurgery)" / "(Family Medicine)" / "(Orthopedics)"; last-name-only convention persists for some categoricals |
| 5. No year in resident schedule date columns | ✅ **Fixed** — every date now reads "Jul 01, 2026" / "Aug 23, 2026" |
| 6. `Include visiting residents` checkbox on single-resident page | ❌ **Unfixed** — still rendered, still does nothing |
| 7. Off-service rotators mixed into PGY-1 group with no distinction | ◐ **Improved** — program-in-parens (#10) means an intern can scan and skip the "(Anesthesia)" / "(Urology)" / etc. entries; no first-class filter |
| 8. Empty-state copy too informal | ✅ **Fixed** — when DB is truly empty, copy now reads "No schedule data is loaded yet. Check back once the next academic year is published." |
| 9. No favicon | ❌ **Unfixed** — still a 404 in console |
| 10. Date picker has no min/max | ❌ **Unfixed** on `/date_picker/`. (Vacation checker date inputs *do* have min/max now, but the date picker page itself does not.) |
| 11. Footer self-deprecation on every page | ❌ **Unfixed** |

**Persona-experience summary:** the intern's blocker — "the site says it's broken" on landing — is gone. The rest of the workflow (picker → resident detail) is also dramatically better:
- Picker shows all 153 entries with PGY group headers.
- Off-service rotators are now labeled instead of being indistinguishable last-names.
- Schedule rows have year on every date.
- Bad URLs land on a recovery page instead of raw FastAPI JSON.

---

## Journey log

### 1. Landed on `/`

What the intern saw on May 14, 2026:
- H1: **"Schedule for Jul 01, 2026"**
- Banner (info-blue): **"No schedule data for May 14, 2026. Showing the next available date — Jul 01, 2026."**
- 5 PGY tabs (PGY 1 / 2 / 3 / 4 / 5), 60 rows total across them

The intern thinks: "OK, I see real data, and the page told me why today is empty." First impression: solid.

### 2. Opened nav → "By Resident"

Picker dropdown with 153 entries. Tom Select renders **all 5 PGY headers** in order. Sample of the first 12 entries (alphabetical within PGY 1):
- "Alec Jonason (Neurosurgery)"
- "Angela Duff" (categorical)
- "Audria Wood (Orthopedics)"
- "Aymin Bahhur" (categorical)
- "Becker (Anesthesia)"
- "Cahill (Anesthesia)"
- "Catalano (Anesthesia)"
- "Cestti (Anesthesia)"
- "Chad Archdeacon (Orthopedics)"
- "Christine Kinstedt (Family Medicine)"
- "Cindy Su (Doctors Hospital)"

The intern can now visually distinguish categorical surgery PGY-1s (no parens) from off-service rotators (program in parens) and Doctors Hospital visitors.

### 3. Picked Sohil Patel → `/resident/?id=37`

- H1: "Schedule for Resident: Sohil Patel"
- Schedule table with year-aware columns: Jul 01, 2026 → Jul 26, 2026, Jul 27, 2026 → Aug 23, 2026, etc.
- Rotation cells are clickable links (`<a href="/rotation/East%20General%20Surgery/?date=2026-07-01">`) that land on the rotation page on the right date.

What still feels off:
- The H1 still reads "Schedule for Resident: Sohil Patel" — no PGY level, no program. Sohil's page is fine for him, but for an off-service rotator like "Brooke" (single name, no first name in the data), the H1 gives no identity context.
- The "Include visiting residents" checkbox is still rendered on the single-resident page — it has nothing to filter, so it just sits there.

### 4. Tried `/resident/?name=foo` directly

Now lands on a friendly error page:
- H1: "That link doesn't look right"
- Lead text: "The page you tried to load is missing some required information."
- Error detail: "id: Field required"
- A list of recovery links: Today's schedule / View by date / View by rotation / View by resident / Check a vacation request

No raw JSON.

---

## Remaining issues (carried over)

### 🟠 Confusing for the persona

1. **Resident detail H1 lacks identity context.** "Schedule for Resident: Brooke" or "Schedule for Resident: Sohil Patel" — should include "(Anesthesia, PGY-2)" or "(General Surgery, PGY-2)" so the persona instantly verifies they're on the right page. (Tier 6 #23.)

2. **`Include visiting residents` checkbox still rendered on `/resident/`.** Single-resident pages have nothing to filter. Hide on this route. (Carryover #6.)

### 🟡 Polish

3. **Date picker (`/date_picker/`) still has no min/max.** Mobile users can spin to 1995 or 2099 and get nothing. The vacation checker page now has min/max scoped to current+next AY; same treatment would help the date picker. (Carryover #10.)

4. **No favicon** — 404 in console. (Carryover #9.)

5. **Footer self-deprecation** still appears on every page. Less harmful now that the empty-state is gone, but still louder than it should be. (Carryover #11.)

6. **Some categorical residents are last-name-only** in the picker (Becker, Cahill, etc. — though those happen to be Anesthesia, so they got the program label). The persona finding called out "Smith"-style cases; spot-checking shows current data has every off-service rotator at least labeled, but a future categorical "Smith" would still be ambiguous. (Carryover #4.)

7. **No "categorical only" filter** on the picker. The intern can now visually skip off-service rotators (parens label), but a one-click filter would be faster. (Carryover #7.)

---

## Issues introduced or noticed for the first time

None blocking. The changes from Batches A–D are all additive or clarifying.

---

## Score-card

- **Original blockers (2):** 2 fixed (empty `/`, 422 JSON).
- **Original confusing (5):** 4 fixed/improved, 1 unfixed (visiting checkbox).
- **Original polish (4):** 1 fixed (empty-state copy), 3 unfixed (favicon, date picker bounds, footer).

The intern persona experience went from "the site is broken" to "I found my schedule in 3 taps." Net score: **major improvement**.
