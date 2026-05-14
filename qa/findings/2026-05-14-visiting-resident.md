# Findings — Visiting Resident (mobile, 390×844) — Re-run

**Run date:** 2026-05-14
**Persona:** Anesthesia PGY-2 resident on a 1-month surgery elective. Persona is "Brooke" (id 54), single Surgical ICU block 2027-03-01 → 2027-03-31.
**Goal:** "Show me just *my* schedule and who I'll be working with."
**Compares to:** [2026-05-12-visiting-resident.md](2026-05-12-visiting-resident.md) — original 11-issue run.

---

## What changed since the original run

| Original issue | Status |
|---|---|
| 1. Off-service rotators identified by last name only in picker | ✅ **Fixed** — Brooke now appears as "Brooke (Anesthesia)" |
| 2. No link from resident's rotation cell into rotation page | ✅ **Fixed** — Surgical ICU cell links to `/rotation/Surgical ICU/?date=2027-03-01` (with the entry's start date) |
| 3. `include_visiting` semantics don't match persona's mental model | ❌ **Unfixed** — Tier 3 #11, deferred (would need a rename + possible split) |
| 4. Resident detail H1 lacks identity context | ❌ **Unfixed** — still "Schedule for Resident: Brooke" with no PGY/program (Tier 6 #23) |
| 5. No year on date columns | ✅ **Fixed** — "Mar 01, 2027" / "Mar 31, 2027" |
| 6. `Include visiting residents` checkbox shown on `/resident/` | ❌ **Unfixed** — still rendered, still does nothing |
| 7. No "where am I" cue on by-date page | ❌ **Unfixed** — Tier 6 #24 |
| 8. No "first day briefing" view | ❌ **Unfixed** — Tier 7 #26 |
| 9. Anesthesia sub-text unlabeled | ◐ **Improved in picker** (parens label); table cells still use the small inline badge but it's at least visually distinguishable |
| 10. No friendly URL slugs | ❌ **Unfixed** — Tier 7 #29 |
| 11. No print/share | ❌ **Unfixed** |

**Persona-experience summary:** the two fixes that landed are exactly the persona's discoverability journey. Brooke can now (a) find herself in the picker by her labeled entry and (b) one-tap from her schedule row to the rotation page on the date she's actually there. The full visiting-resident workflow now functions end-to-end:

1. Picker → "Brooke (Anesthesia)" — confidently her
2. Resident detail → "Surgical ICU" link with year-aware dates
3. Click → `/rotation/Surgical ICU/?date=2027-03-01` showing her with her co-residents

---

## Journey log

### 1. Picker

Sample of PGY 2 entries Brooke might scan past on her way to herself:
- ... Bar-Meir, Brooke (Anesthesia), Brown (Anesthesia), Burgmaier (Anesthesia), Churma (Anesthesia), ...

The "(Anesthesia)" label gives her confidence that the bare last name is in fact her, not some categorical surgery resident she doesn't know. Compared to the original where "Brooke" was an indistinguishable single name, this is the persona's most-felt change.

### 2. Resident detail `/resident/?id=54`

- H1: "Schedule for Resident: Brooke" — still no program/PGY context (carryover #4)
- Schedule table: Brooke / Anesthesia | Surgical ICU | **Mar 01, 2027** | **Mar 31, 2027** | (empty vacation cell)
- Surgical ICU cell is now a **link** — `<a href="/rotation/Surgical%20ICU/?date=2027-03-01">`
- "Include visiting residents" checkbox still rendered — does nothing on a single-resident page (carryover #6)

### 3. Tapped Surgical ICU → `/rotation/Surgical ICU/?date=2027-03-01`

Lands directly on the right rotation, on her start date. She sees:
- All 5 PGY tabs (since SICU has residents at every level)
- Her PGY 2 tab includes Brooke (Anesthesia), Brown (Anesthesia), Churma (Anesthesia), and the categorical PGY-2 Olivia Duru
- Other off-service rotators (Stammen Anesthesia, Furrukh Plastic Surgery, Audria Wood Orthopedics, Katelyn Sette Orthopedics) appear in their PGY tabs

She can now answer "who am I working with this month" in 2 taps from her detail page.

### 4. What still doesn't exist

- A "first day briefing" hub view (Tier 7 #26) — single page with dates + co-residents + (eventually) attending + call schedule.
- Disambiguated `include_visiting` semantics for off-service vs. institutional. The toggle still says "Include visiting residents" without clarifying what counts.
- Friendly URL slug — sharing her page still requires `/resident/?id=54`.

---

## Remaining issues (carried over)

### 🟠 Confusing for the persona

1. **Resident detail H1 lacks identity context.** Should be "Brooke (Anesthesia, PGY-2)". (Carryover #4, Tier 6 #23.)

2. **`include_visiting` semantics don't match.** Brooke considers herself "visiting"; the system reserves the term for institutional visitors only. (Carryover #3, Tier 3 #11.)

3. **`Include visiting residents` checkbox on single-resident page.** (Carryover #6.)

### 🟡 Polish

4. **No "where am I" cue on by-date page** — default tab isn't always the persona's PGY. (Carryover #7, Tier 6 #24.)

5. **No "first day briefing" view.** (Carryover #8, Tier 7 #26.)

6. **No friendly URL slugs.** (Carryover #10, Tier 7 #29.)

7. **No print/share.** (Carryover #11.)

---

## Issues introduced or noticed for the first time

None.

---

## Score-card

- **Original blockers (2):** 2 fixed (picker label, rotation cell link).
- **Original confusing (5):** 1 fixed (year), 1 improved (program label in tables), 3 unfixed (H1, visiting toggle semantics, checkbox on resident page).
- **Original polish (4):** 0 fixed; all 4 are deferred Tier 6/7 items.

The discoverability blockers are gone — Brooke can find herself and navigate to her co-residents. The remaining work is polish (H1 label) and larger features (first-day briefing). Net: **major improvement on the primary workflow.**
