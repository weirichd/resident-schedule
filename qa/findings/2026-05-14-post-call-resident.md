# Findings — Post-Call Resident (mobile, 390×844) — Re-run

**Run date:** 2026-05-14
**Persona:** PGY-3 just finished a 24h shift. Phone in one hand, coffee in the other.
**Goal:** "Who's covering ACS tomorrow? I have to hand off a patient before I leave."
**Compares to:** [2026-05-12-post-call-resident.md](2026-05-12-post-call-resident.md) — original 9-issue run.

---

## What changed since the original run

| Original issue | Status |
|---|---|
| 1. No date selector on rotation page | ✅ **Fixed** — date input added; populated with current view date; submitting jumps to that date |
| 2. "Coming Next" silently drops PGY tabs with no data | ✅ **Fixed** — Coming Next is padded to share PGY tabs with Current; missing PGYs render "No PGY X residents in this section." |
| 3. `include_visiting` semantics ambiguous on rotation page | ❌ **Unfixed** — still labeled "Include visiting residents" with no clarification on whether off-service rotators count |
| 4. Off-service rotator's home program not labeled | ◐ **Improved** — table cells now show e.g. "Drayson Campbell Vascular Surgery" with the program as a small inline badge; *picker* also labels them now |
| 5. Mixed elective sub-types in rotation picker | ❌ **Unfixed** — Cardiac/Gyn/IR/MIS still in the flat rotation list |
| 6. Naming collisions in picker (Endocrine vs. Breast and Endocrine; Outpatient vs. Outpatient SONC) | ❌ **Unfixed**, but **the underlying confusion is resolved** — the prefix-match bug that made Breast page absorb Breast-and-Endocrine residents (Tier 1 #1) is fixed, so the names are accurate. The picker still presents both, but each one now navigates to a coherent page. |
| 7. No year in Starting/Until columns | ✅ **Fixed** — every date now reads "Sep 21, 2026" / "Oct 18, 2026" |
| 8. No "next rotation per resident" link from Current rows | ❌ **Unfixed** — would still take a click into the resident's full schedule |
| 9. No deep link from "By Date" view to a specific rotation on that date | ◐ **Partially fixed** — by-date schedule rows now have rotation cells linking to the rotation page on that entry's start date. (Still no "By Date → rotation on this exact date" deep link, but the new link at least gets the user to the right rotation.) |

**Persona-experience summary:** the persona's #1 blocker — "no way to pick a different date" — is gone. The post-call resident can now answer "who's on ACS tomorrow" in 2 taps (open rotation page → tap date picker → pick tomorrow) instead of having to type a URL.

---

## Journey log

### 1. Landed on `/`

`/` falls through to Jul 01, 2026 with the info banner — no longer a dead end.

### 2. Tapped "By Rotation" → "Acute Care Surgery"

Rotation page opens at today's date (Sep 15 in this test). Both Current and Coming Next show **PGY 1 / 2 / 4 / 5** tabs (consistent — both sections have the same set, with empty tabs rendered with a friendly message).

The post-call resident's actual question is "tomorrow," so they need to change the date.

### 3. Used the new date input

A "Show date" date input appears below the rotation header, pre-populated with today's date. Picking Sep 16 reloaded the page at `?date=2026-09-16`. One tap.

The Sep 16 view shows:
- **Current PGY 1:** Shaheen (Plastic Surgery), Grant Sajdak (Urology)
- **Current PGY 2:** Alexandra Barone-Campos, Preethy Sridharan, Youssef Aref, Drayson Campbell (Vascular Surgery)
- **Current PGY 4:** Stefanie Rhode
- **Current PGY 5:** Pat Quinn
- **Coming Next PGY 1:** Michelle Garrison, Furrukh (Plastic Surgery)
- **Coming Next PGY 2:** Morgan White, Olivia Duru, Youssef Aref, Divyaam Satija (Cardiothoracic Surgery)

The off-service rotator labels (Plastic Surgery / Urology / Vascular Surgery / Cardiothoracic Surgery) are right there inline. The post-call resident handing off a patient knows immediately whether the receiving resident is a categorical PGY-2 (Alexandra Barone-Campos) or off-service (Drayson Campbell, vascular).

### 4. Vacation visibility

The Vacation/Conference column is always present now (no longer conditionally hidden). For ACS Sep 16, there happen to be no active vacations on this date — empty cells, but the column header is there as a stable structural element.

---

## Remaining issues (carried over)

### 🟠 Confusing for the persona

1. **`include_visiting` semantics still unclear.** The toggle filters institutional visitors (Doctors Hospital), not off-service department rotators (Anesthesia/Urology/Plastics/Ortho). The label doesn't say which. (Carryover #3.)

### 🟡 Polish

2. **No "next rotation per resident" link** from Current rows. The post-call resident wanting to know what the current ACS senior rotates to next has to click through to that resident's full schedule. (Carryover #8.)

3. **Mixed elective sub-types in rotation picker** (Cardiac, Gyn, IR, MIS, OB, Ortho, Plastics, Rural, Hernia next to real services). Hasn't been touched. (Carryover #5.)

4. **Picker still has Endocrine vs. Breast and Endocrine and similar near-collisions.** Now that the prefix-match bug is fixed, picking either one shows coherent data — but the picker offers no help disambiguating. (Carryover #6.)

---

## Issues introduced or noticed for the first time

None. The post-call workflow is now genuinely fast.

---

## Score-card

- **Original blockers (1):** 1 fixed (date selector).
- **Original confusing (5):** 2 fixed (Coming Next, year), 2 improved (off-service labeling, naming collisions less harmful), 1 unfixed (visiting toggle).
- **Original polish (3):** 1 partially fixed (deep links), 2 unfixed.

Net: **major improvement on the primary use case.** The persona can now actually do their job from the rotation page.
