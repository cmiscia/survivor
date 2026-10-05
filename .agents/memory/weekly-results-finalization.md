---
name: Weekly results finalization
description: League rule for handling missing picks when weekly outcomes are posted.
---

Post Results is the sole end-of-week operation. It must first assign an
automatic loss to every active user without a pick for that week, then fetch
game winners and update outcomes.

**Why:** Once every game has started, a player cannot submit a valid pick.
Requiring a separate finalization action allowed results to be posted without
recording missed-pick losses.

**How to apply:** Keep missing-pick creation and outcome posting combined and
repeatable. Refuse to post results while any selected-week game remains
available.