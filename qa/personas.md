# QA Personas

A set of user personas for exploratory testing of the resident schedule viewer. Each persona has a specific goal, a mental model, and a journey script — the point is to test goals, not pages.

Runs are driven via the Playwright MCP against the local dev server (`http://127.0.0.1:8000`). Findings for each run are written to `qa/findings/<date>-<persona-slug>.md`.

---

## 1. The Brand-New Intern

**Who:** PGY-1 on day 1 of residency. Has never used this app before. Doesn't yet know the difference between "Burn" and "Acute Care Surgery" or whether they count as a "visiting" resident.

**Viewport:** Mobile (390 × 844 — iPhone-ish).

**Goal:** "Where am I supposed to be Monday morning?"

**Mental model:**
- I just got an email saying "check the schedule." I have no bookmark, no insider knowledge.
- I'm looking for *my name* and *today/tomorrow*.
- I don't know what a "rotation" is in this app's sense vs. the curriculum sense.

**Journey:**
1. Land on `/` cold.
2. Try to figure out what I'm looking at and where I'd find my own schedule.
3. Look for a way to filter to *just me*.
4. Note any jargon, empty states, or affordances that don't match an intern's vocabulary.

**Surfaces:** discoverability, mobile layout, name picker UX, distinction between visiting/prelim and categorical, empty-state copy.

---

## 2. The Post-Call Resident

**Who:** PGY-3 just finished a 24h shift. Phone in one hand, coffee in the other. Knows the app, hits it often.

**Viewport:** Mobile (390 × 844).

**Goal:** "Who's covering ACS tomorrow? I have to hand off a patient before I leave."

**Mental model:**
- I want the answer in <10 seconds.
- I know the rotation name ("ACS"), I know roughly what date.
- I'd rather click 1-2 things than type.

**Journey:**
1. Land on `/`.
2. Navigate to ACS tomorrow as fast as possible.
3. Identify the covering senior + intern.
4. Check whether the resident I want to hand off to is on vacation.

**Surfaces:** speed of common queries, date defaults, mobile tap targets, rotation discoverability, vacation visibility on rotation page.

---

## 3. The Breast Attending

**Who:** Attending physician on the Breast service. Plans her week around resident continuity. Uses a desktop in clinic between cases.

**Viewport:** Desktop (1440 × 900).

**Goal:** "Who's on my service right now, when do they rotate off, and is anyone going on vacation in the next 2 weeks?"

**Mental model:**
- "My service is Breast." Does not distinguish "Breast" from "Breast and Endocrine" — that's a scheduler concept, not a clinical one.
- Cares about *her people*, not other services.
- Wants forward visibility: 2-4 weeks ahead.

**Journey:**
1. Land on `/`.
2. Navigate to the Breast rotation view.
3. Notice: is "Breast" the same as "Breast and Endocrine"? Are residents split? Mislabeled?
4. Identify who's on now, when they rotate off, who comes next.
5. Check whether any current resident has vacation scheduled in the next 2 weeks.

**Surfaces:** rotation naming consistency (Breast vs. Breast and Endocrine), rotation timeline, upcoming-vacation surfacing, attending-oriented use case (vs. resident-centric).

---

## 4. The Vacation Planner *(deferred)*

**Who:** PGY-2 planning a wedding.

**Goal:** "I want Aug 10-14 off. Will it conflict? Am I on a no-vacation rotation?"

**Notes:** Requires the vacation checker flow. Run once that feature has a stable UI surface.

---

## 5. The New Service Chief *(deferred)*

**Who:** Newly appointed Colorectal service education liaison.

**Goal:** "Show me everyone rotating through CRS for the next 3 months and flag any vacation overlaps."

**Notes:** Tests long-range rotation view and vacation-overlap visibility.

---

## 6. The Visiting Resident *(deferred)*

**Who:** Anesthesia resident on a 1-month surgery elective.

**Goal:** "Show me just *my* schedule and who I'll be working with."

**Notes:** Tests `include_visiting` filter behavior and visiting-resident discoverability.
