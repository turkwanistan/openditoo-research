# OpenDitoo P3 product evidence closure — 2026-09-09

## Decision

P3 is closed pragmatically for MCP Dashboard v1. The owner reports the persistent dashboard is working well in normal use and has been actively using/testing it with MCP calls. A fresh read-only state check during this closure also showed the normal collector continuing to advance under product operation: WSL MCP was healthy/green with activity sequence 615 and a 2026-09-09T19:33:13Z last-activity stamp; Lab was healthy with sequence 26; OptiPlex MCP was healthy with sequence 29. This is product-mode source activity evidence, not a synthetic device trial.

No new experimental transmission was created for P3. The standing Runtime 001 product authority already owns the normal dashboard loop.

## Source activity — accepted for v1

Normal MCP-source activity while the persistent product runtime owns the display is accepted for v1 based on continued owner use plus live collector advancement. This complements Activation 007, which already physically proved a genuine WSL_MCP event drives the accepted three-sweep animation through the same renderer/session stack.

## Fault path — accepted for v1 without disrupting a healthy Lab

Activation 009 physically accepted the real production renderer/wire/display fault presentation on the exact Ditoo: healthy grey/no bar -> simulated `source_health=unavailable` -> grey + dim-red crown bar -> healthy grey/no bar.

A deliberately induced outage of the real Lab service is **waived**, not falsely claimed. Breaking a healthy Lab, SSH path, or source service solely to repeat the already accepted visual path has low product value and would create unnecessary disruption. The collector already has offline coverage for failed reads -> `unavailable`, stale aging, recovery, and source isolation.

Therefore v1 claims:

- normal persistent product source activity: accepted;
- source-failure state machine: offline verified;
- fault renderer/wire/physical display path: accepted on hardware;
- genuine production Lab outage: not separately induced and not claimed as a distinct hardware experiment.

This is sufficient for the owner's requested v1 wrap-up. Future real outages may be recorded opportunistically if they occur naturally; they are not a release blocker.
