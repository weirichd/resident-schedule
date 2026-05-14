# Findings — Breast Attending (desktop, 1440×900) — Re-run

**Run date:** 2026-05-14
**Persona:** Attending physician on the Breast service. Plans her week around resident continuity.
**Goal:** "Who's on my service now, when do they rotate off, and is anyone going on vacation in the next 2 weeks?"
**Compares to:** [2026-05-12-breast-attending.md](2026-05-12-breast-attending.md) — original 9-issue run that surfaced the prefix-match bug.

---

## What changed since the original run

| Original issue | Status |
|---|---|
| 1. Asymmetric prefix matching → Breast page absorbs Breast and Endocrine residents | ✅ **Fixed** — `/rotation/Breast/` shows only Breast residents; `/rotation/Breast and Endocrine/` correctly shows the PGY-4 (Diamantis Tsilimigras) |
| 2. Two sections same page use different match logic | ✅ **Fixed** — both Current and Coming Next now use exact match |
| 3. No forward-vacation view (next 2 weeks of vacations on this service) | ❌ **Unfixed** — still need to scan each row's vacation cell |
| 4. No 2-4 week look-ahead | ❌ **Unfixed** — Coming Next is still single-block per PGY |
| 5. Rotation column shows "Breast and Endocrine" on Breast page | ✅ **Fixed** as a side effect of #1 — that PGY-4 row no longer appears on the Breast page at all |
| 6. Date hard-coded to today, no UI to change | ✅ **Fixed** — date input on the rotation page |
| 7. No year in date columns | ✅ **Fixed** |
| 8. Visiting checkbox ambiguity | ❌ **Unfixed** |
| 9. Rotation picker mixes electives and services | ❌ **Unfixed** |

**Persona-experience summary:** the headline correctness bug (the attending getting an unexpectedly mixed roster on the Breast page) is gone. The two services now navigate to coherent, accurate pages. The remaining work is forward-visibility (the larger Tier 4 features), which we've intentionally deferred.

---

## Journey log

### 1. `/rotation/Breast/?date=2026-09-15`

What the attending sees:

| PGY | Resident | Rotation | Starting | Until | Vacation/Conference |
|---|---|---|---|---|---|
| 1 | Jasmine Jones | Breast | Aug 24, 2026 | Sep 20, 2026 | — |
| 2 | Sohil Patel | Breast | Aug 24, 2026 | Sep 20, 2026 | — |

Coming Next: Vikas Munjal (PGY 2), starting Sep 21, 2026 → Oct 18, 2026.

**No PGY-4 row.** The Diamantis row that previously appeared (because of the prefix bug) is gone. Current matches the actual Breast roster.

### 2. `/rotation/Breast and Endocrine/?date=2026-09-15`

| PGY | Resident | Rotation | Starting | Until | Vacation/Conference |
|---|---|---|---|---|---|
| 4 | Diamantis Tsilimigras | Breast and Endocrine | Aug 17, 2026 | Oct 04, 2026 | Vac: Aug 17, 2026–Aug 23, 2026 |

Coming Next: Ali Whalen (PGY 4), Oct 05 → Nov 15. The previously-empty page now correctly shows the resident assigned to this service.

The attending who picks "Breast and Endocrine" from the picker no longer sees a blank page; the Endocrine attending experience is fixed.

### 3. Forward visibility — still limited

The attending's "anyone on vacation in the next 2 weeks?" question still requires scanning each row's vacation cell. The current display does at least show vacations *during* the chosen date's block (Diamantis's Aug 17–23 vacation appears even though we're viewing Sep 15, because Diamantis's block extends backward to Aug 17). But there is no consolidated "next 14 days of vacations on this service" panel.

Coming Next still surfaces one block ahead, which is fine for a 4-week service like Breast (~1 transition per PGY) but not enough for a chief asking about the next quarter.

### 4. Date input

Pre-populated with the current view date. Picking a different date jumps the page. Same workflow as the post-call resident.

---

## Remaining issues (carried over)

### 🟠 Confusing for the persona

1. **No forward-vacation panel.** The persona's question — "anyone on vacation in the next 2 weeks?" — still requires reading every row. (Carryover #3.)

2. **No 2-4 week look-ahead.** Coming Next is one block. (Carryover #4.)

### 🟡 Polish

3. **Visiting checkbox ambiguity.** Same as other personas. (Carryover #8.)

4. **Rotation picker mixes electives and services.** (Carryover #9.)

---

## Issues introduced or noticed for the first time

None.

---

## Score-card

- **Original blocker bugs (1):** 1 fixed (prefix match — the headline bug from this persona).
- **Original confusing (5):** 2 fixed (date selector, rotation column display), 3 unfixed (forward vacation, look-ahead, visiting toggle).
- **Original polish (4):** 1 fixed (year), 3 unfixed.

The correctness bug that made this persona's pages actively misleading is fixed. The remaining work (forward visibility) is the bigger Tier 4 design effort that hasn't been started yet.
