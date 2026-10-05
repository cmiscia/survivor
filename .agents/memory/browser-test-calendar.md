---
name: Calendar-independent browser tests
description: Why browser smoke tests must not depend on a fixed season date.
---

Browser smoke tests must remain valid before, during, and after the NFL season.
Exercise next-unpicked-week defaults with a player who has a gap in loaded weeks;
keep selectable fixture games relative to the test run date.

**Why:** A browser fixture with every loaded week already picked falls back to
the current calendar week. A fixed Week 1 assertion then starts failing as the
season progresses, even when production behavior is correct. Fixed future
kickoff dates likewise eventually lock the test's selectable teams.

**How to apply:** Keep calendar-sensitive fallback behavior in focused tests
with controlled time. Do not change production week selection to satisfy a
dated browser fixture.