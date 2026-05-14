# Findings — Breast Attending (desktop, 1440×900)

**Run date:** 2026-05-12
**Persona:** Attending physician on the Breast service. Plans her week around resident continuity. Sits at a desktop between clinic cases.
**Goal:** "Who's on my service now, when do they rotate off, and is anyone going on vacation in the next 2 weeks?"
**Environment:** Local dev server, desktop viewport. Probed the date 2026-09-15 because "today" is empty.

> Same starting-point blocker as the other personas: `/` shows no data on 2026-05-12. Already captured in the new-intern findings. This run focuses on what the attending sees once they navigate to her rotation.

---

## Journey log

### 1. Navigated to By Rotation → "Breast"

The attending's mental model is **"My service is Breast"** — she does not normally distinguish "Breast" from "Breast and Endocrine." Both are her service from a clinical standpoint.

In the picker she sees both entries listed:
- "Breast"
- "Breast and Endocrine"

She picks "Breast" because that's the word she uses.

### 2. `/rotation/Breast/?date=2026-09-15` — **active "bug" that accidentally helps her**

What she sees on the "Current" panels:

| PGY | Resident | Rotation column reads | Vacation column |
|---|---|---|---|
| 1 | Jasmine Jones | Breast | — |
| 2 | Sohil Patel | Breast | — |
| 4 | Diamantis Tsilimigras | **Breast and Endocrine** | Vac: Aug 17–Aug 23 |

This **matches her mental model exactly** — all three are on her service. But here's the catch: the Rotation column for the PGY 4 reads "Breast and Endocrine," not "Breast." Her eye snags on that. She thinks: *Is Diamantis actually on my service, or is this a UI bug? Should I be staffing him?*

The answer is: yes, he's on her service, but only by accident of how the page filters.

### 3. Confirmed it's an accident: `/rotation/Breast and Endocrine/?date=2026-09-15` is empty

Same date, the explicit "Breast and Endocrine" rotation page shows **zero residents** in both Current and Coming Next sections.

This means:
- The Breast page is using **prefix matching** to filter the "Current" section (`app/app.py:315`: `current = [e for e in entries if e["rotation"].startswith(rotation_name)]`).
- "Breast and Endocrine" `.startswith("Breast")` → true → included on the Breast page.
- "Breast" `.startswith("Breast and Endocrine")` → false → excluded on the Breast and Endocrine page.
- The match is **asymmetric**. The shorter name "wins" and silently pulls in the longer one's residents.

**Implications across the app:**
- `/rotation/Breast/` shows Breast + Breast-and-Endocrine. `/rotation/Breast and Endocrine/` shows only Breast and Endocrine. Always favoring the Breast page.
- `/rotation/Outpatient/` will silently include Outpatient Surgical Oncology rotations. (Confirmed nothing's on Outpatient on the date I checked, but the prefix logic is the same.)
- If any rotation name is a prefix of another, the shorter one silently absorbs the longer one. This is a *vacation-checker-relevant* concern — the call-pool logic uses exact equality, but a human eyeballing the rotation page might think "no one's available" or "everyone's available" based on the wrong set.

### 4. "Coming Next" section uses exact match

Spot-checked: `get_coming_next_entries()` (line 318) filters by `Schedule.rotation == rotation_name` exactly. So Coming Next on the Breast page does *not* show Breast-and-Endocrine residents. The two sections on the same page use different match logic — and that's the inconsistency that triggers the attending's confusion.

### 5. Vacation visibility

The Vacation/Conference column is great in concept — Diamantis's row shows "Vac: Aug 17–Aug 23" inline.

But the attending's actual question is "anyone going on vacation in the next 2 weeks?" — i.e., from any of *her* people, between today and 2 weeks out. The current page only shows vacations attached to people listed in Current. If a resident has a vacation request in the relevant date range but their block straddles the chosen date in a way the "Current" filter doesn't catch, the vacation won't surface.

There is also **no "upcoming vacations on this service in the next N days" view** anywhere in the app. The attending has to read it off of each row manually.

### 6. Forward visibility limited to "next 1 block per PGY"

The Coming Next section shows only the *next* assignment per PGY. The attending wants to think 2–4 weeks out; the page can only show "right now" and "the one after that." For Breast (a typical 4-week block), this gives some forward view, but it's not a real planning view.

### 7. Naming asymmetry in the picker compounds confusion

The picker offers separate "Breast" and "Breast and Endocrine" entries. Most attendings don't think in scheduler-rotation names. Picking either one gives a different view of the world, and there is no on-page acknowledgement of the other.

The Endocrine attending (if one were running this exercise) would have an even worse experience: a rotation page that pulls in nothing.

---

## Issues, by severity

### 🔴 Blocker bugs

1. **Asymmetric prefix matching on the rotation Current section.** `app/app.py:315` uses `.startswith(rotation_name)`, which collapses any rotation whose name prefixes another. Affects at least Breast / Breast and Endocrine, and Outpatient / Outpatient Surgical Oncology. The Endocrine attending sees zero residents on Breast and Endocrine despite residents being assigned to it.
   - Fix: change to `e["rotation_raw"] == rotation_name` (the entries already carry `rotation_raw` per `app/app.py:150`). Or use an explicit `(rotation, location)` equality.
   - **Bonus question:** decide whether Breast and Breast-and-Endocrine should *intentionally* be treated as the same service from the attending's view. If yes, build an explicit service-group abstraction (the vacation rules already have one — `SERVICE_GROUPS` in `app/vacation_checker.py:14`). Reuse it here.

### 🟠 Confusing for the persona

2. **Two sections on the same page use different match logic.** Current = prefix match; Coming Next = exact match. Even after fixing the bug, the two sections should obviously share the same filter.

3. **No forward-vacation view.** "Anyone on vacation in the next 2 weeks from my service?" requires reading every row's vacation cell. A separate small panel ("Upcoming vacations: 2 in the next 14 days") would be high-value for attendings specifically.

4. **No 2–4 week look-ahead.** Coming Next = "the next block." For block-based planning that's not enough. A timeline view of the next 2 months (one row per resident, shaded by block) would change the attending's life.

5. **Rotation column shows "Breast and Endocrine" on the Breast page.** Even after fixing the underlying bug, the choice of *what to display* in the Rotation column matters. If the answer is "show me Breast people," the column shouldn't display divergent rotation names that make the user question whether the row belongs there.

### 🟡 Polish

6. **Date is hard-coded to "today" in the page subtitle and there's no UI to change it.** Same finding as the post-call resident.

7. **No year in date columns.** Same finding as the other personas.

8. **The visiting-residents checkbox** has the same ambiguity flagged elsewhere — for an attending the relevant filter is "rotators from outside the surgery program," not "visiting from outside the institution."

9. **The rotation picker still mixes electives and services with no grouping.** Less acute for the attending (she searches a specific name) but real.

---

## Suggested fixes (rough ranking by impact)

| # | Fix | Files |
|---|---|---|
| 1 | Change `current = ... startswith(rotation_name)` → exact match on `rotation_raw` | `app/app.py:315` |
| 2 | Decide whether to introduce a "service group" abstraction shared between rotation view and vacation checker. If yes, define groups once (`SERVICE_GROUPS`) and have the rotation view query the group. | `app/app.py`, `app/vacation_checker.py:14` |
| 3 | Add a "Upcoming Vacations" panel on the rotation page (next N days of vacations for anyone scheduled on this rotation in that window) | `app/app.py`, new section in template |
| 4 | Add a date input to the rotation page (shared with post-call findings) | `app/templates/rotation_detail.html` |
| 5 | Add a 4-week / 8-week forward timeline on the rotation page | new view, larger work |
| 6 | Normalize rotation-column display on rotation pages to the chosen view (don't show "Breast and Endocrine" on the Breast page if you've decided they're one service) | template + display layer |
| 7 | Year in date columns | `prepare_table()` |
