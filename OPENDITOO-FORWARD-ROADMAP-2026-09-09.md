# OpenDitoo forward roadmap

Date: 2026-09-09. Authoritative checkout: `/home/wan/Projects/openditoo-research`, branch `main`, HEAD `d957bdae47cf926da4d39d805ec5e4e78f9dee48`. Worktree clean before and after inspection. Planning only: no device transmission, deployment, authority mutation, or repository modification was performed.

## Recommendation

Finish the existing MCP activity application as an explicitly activated, bounded display session. First close its authority lifecycle and receive/fault handling offline; then validate it on the exact unit from a capable environment under a new named grant. Install collection independently of display authority, qualify longer operation incrementally, and release a narrow exact-unit product. Stop there unless actual use establishes a valuable next application.

This is a useful low-rate status display, not yet a general animation platform. M0–M8 do not need repeating. The most valuable remaining reverse engineering concerns stock takeover and long-session behavior, because those affect the application directly. ACK-byte decoding, speculative physical navigation, and MassBoot are not prerequisites.

Milestone IDs below are roadmap labels, not experiment IDs and not transmission authority. Effort estimates are engineering time excluding operator scheduling: XS = under two hours, S = roughly half a day, M = one to three days, L = several days or open-ended. Confidence describes the proposed path, not unearned device proof.

## Verified baseline and environment

Hydration followed the requested order: handoff, AGENTS, Git history/status, offline verifier, then targeted milestone evidence and implementation. No external research or OpenTivoo checkout access was needed: exact-unit sources already answer the planning questions.

| Check | Observed result | Planning consequence |
| --- | --- | --- |
| Git | `main` at `d957bda`; clean | Preserve this baseline; recheck before implementation because concurrent work may arrive. |
| `python3 scripts/verify_day1_offline.py` | PASS: 19 artifacts, 79 tests, `host=typed_image`, port 8796, `device_io=false`; M4/M5 unauthorized | Offline baseline is healthy; this is not a Windows build or live acceptance. |
| `command -v powershell.exe` | Exit 1, no output | No Windows shell bridge found in this sandbox. |
| `python3 cli/openditoo.py status` | MCP transport returned HTTP 504, request timed out; no CLI result obtained | Host reachability and installed identity are unverified here. Do not interpret this as proof that the Host is down. |
| `python3 cli/openditoo.py activity-probe` | CLI returned `ok:true`, but all three sources were `reachable:false`, `SOURCE_READ_FAILED`; `device_io:false` | Probe execution succeeded; source access did not. Even the local WSL audit source is unavailable in this sandbox. |
| Execution context | bubblewrap, `write_scope=none`, network off for inspection | Repository inspection and Python verification work; remote source integration does not. |

No separate SDK or SSH success is claimed. Windows compilation/deployment requires another verified-capable environment; source integration requires actual read access to the configured logs/journal. Do not widen sandbox permissions or alter source access controls merely to make this session pass. A local WSL/Windows session is a candidate environment, not a guaranteed capability.

The collector itself reads files/journals and does not generate MCP calls. This session's WSL_MCP calls, however, can be recorded in the monitored audit source. When access is restored, distinguish known test calls and this agent's footprint from independent user activity. Do not add an attribution subsystem merely because the observer used MCP during verification.

### Completed work to retain

| Area | Accepted evidence | Limits to retain |
| --- | --- | --- |
| M0–M5 | Exact-unit transport/version and first visible custom frame | Authorities consumed; no transfer from Tivoo. |
| M6 | Typed PNG path, Python/C# encoding agreement, fixed target, diagnostics, installed Host acceptance, physical geometry | Host startup is already installed; do not recreate it. Current installation was not reverified here. |
| Display persistence | Custom frame disappears across power cycle; stock clock returns | This does **not** prove no nonvolatile writes occurred. |
| M7 | Controls produce state reports; arrows/joystick silent under tested official-app context | Completed bounded negative for navigation; not proof of silence under every possible context. |
| M8 | Same-connection repeated full three-packet frame groups, two ten-frame transport passes, zero missing ACKs/errors | Approximately 1118 ms/frame accepted; only about ten seconds per loop, not long-term reliability proof. Ten-frame visual order still pending. |
| M9 offline | Three adapters, normalization, cursors, bounded reads, restart seeding, error isolation, atomic compact state, renderer and preview CLI | No installed worker or live activity display. Lab source is forwarded-command activity, not tool completion. |
| Preservation | Hash-verified artifacts, private capture exclusions, sanitized evidence and endpoint placeholder checks | Raw bugreports/btsnoop and real endpoints remain private. |

The repository renderer is three horizontal bands with server/flask/W glyphs, age fields and separate health indicators. It is not the separate bunny/mushroom/skull design from chat history. Retain the repository renderer for first activation; any artwork migration needs an explicit later product decision and actual assets. Ditoo's proven path uses RGB888 palettes, not a mandatory Tivoo RGB222 palette.

## Contradictions and stale statements

1. **Handoff snapshot:** `b86dfcb` and 78 tests are stale; current HEAD is `d957bda`, 79 tests. The subsequent commits concern handoff/routing/capability wording, not a completed M9 activation.
2. **Authority wording:** AGENTS still permits an explicitly invoked static `image-show` transaction without the new-manifest wording. START_HERE, the handoff, and this task require a new manifest plus a grant naming its experiment ID for every live operation. Apply the stricter rule. Reconcile the docs before implementation; do not exploit the older exception.
3. **Host scope:** AGENTS describes only a static-image route, while `Program.cs` advertises `image-sequence` and implements `/v1/image/sequence`. Record the already accepted bounded sequence capability without suggesting ongoing authority.
4. **Installed Host:** older START_HERE/PROJECT_STATE passages say the installed Host may still be status-only. M6 and later M8/handoff evidence supersede that historical uncertainty. Current installed bytes remain unverified from this environment; neither reinstall nor declare them broken based on the timeout.
5. **M8/M9 historical notes:** M8's earlier “any loop not built” and M9's “waiting on M7/M8” paragraphs are superseded by the consumed finite-loop results and M7 negative result. Keep them as dated history or add explicit supersession pointers.
6. **M6 acceptance table:** its trailing statement that orientation/persistence remain unconfirmed conflicts with the later physical findings in the same note. Geometry and display volatility are confirmed; complete color rendition and absence of nonvolatile writes are not.
7. **M7 payload transcription:** the key-sweep JSON's derived `data_bytes` is 22 for the observed `0x46` report, but its finding prose still says 21. Keep `wire_hex` authoritative and correct only the derived prose; do not change raw evidence to fit a sentence.
8. **Authority enforcement depth:** the inspected `sequence_run` checks manifest flags but does not atomically consume/reserve authority itself; its Host request carries frames and budgets, not an experiment identity. The Host enforces typed operations and ownership, but the inspected route is not an end-to-end durable manifest-consumption gate. Historical manual consumption is adequate evidence of past bookkeeping, not proof of crash-safe automatic activation. This is a productization gap, not authorization to exercise the route.

## Next horizon — finish the offline boundary and earn first activation

### N1 — Reconcile current state and acceptance gaps

- **Objective/value:** make the next implementor's route unambiguous; very cheap protection against repeating completed experiments or misreading authority.
- **Confidence/effort:** high, XS.
- **Dependencies/environment/authority:** existing evidence only; offline in WSL_MCP, no grant required.
- **Work:** update current routing and authority wording; explicitly supersede stale paragraphs above; preserve immutable capture bytes and historical results. Record current HEAD/verifier evidence. Keep the older reconstruction research labeled historical.
- **Evidence closed:** documentation contradictions, not new device behavior. Ask once, when an operator is next available, whether they actually observed the prior ten-frame alternation/order. A recollection must be attributed as such. If they cannot confirm, leave it pending and obtain visual acceptance during the new M9 trial rather than repeat M8 just for bookkeeping.
- **Exit:** one consistent current-state route; old grants remain consumed; no claim that ACKs establish visual order; relevant documentation no longer proposes M0–M8 again.

### N2 — Specify and implement a bounded activity-session authority lifecycle

- **Objective/value:** safely join changing activity frames to the existing typed image primitive. High value and prerequisite to any automatic display.
- **Confidence/effort:** high for offline design; medium for integration, M.
- **Dependencies/environment/authority:** N1; offline source work and fake-transport verification here. Windows build later requires a capable environment. No grant needed to implement; all activation artifacts remain disabled.
- **Work:** introduce the smallest explicit session contract: experiment ID, exact unit/firmware, source and renderer version hashes, fixed typed encoding, activation source, expiry/lifetime, packet/frame/byte ceilings, conservative pacing, one connection attempt, no retry/reconnect, stop conditions and result receipt. Bind runtime-generated frames to the reviewed renderer/state envelope and verify each frame's Python/C# hash before sending; a dynamic app cannot pretend all future pixels were frozen in a static frame list.
- **Work:** claim the experiment durably before dispatch, reject concurrent claims and already attempted/consumed/expired IDs, and preserve an ambiguous result across worker/Host restarts. Bind Host activation to the reviewed session identity. Use a small atomic local record, not a job platform or database. Keep authentication separate from permission to transmit.
- **Work:** ensure the Host itself enforces lifetime and budgets if the worker disappears; client cancellation or an HTTP timeout must not silently authorize continued sends or a second request. Process startup creates no display authority. A failed/uncertain attempt needs a fresh manifest and named grant, never a reset flag.
- **Capability closed:** the difference between a frozen finite list and a bounded app-driven session, including durable one-use authority. Existing static/sequence routes must not become alternate automation paths.
- **Exit:** offline cases prove zero dispatch for missing/expired/consumed authority, duplicate activation, hash drift and invalid budgets; crash/restart does not resume or replay; each attempted session has a bounded terminal or explicitly unknown record. No live grant is asserted.

### N3 — Add takeover-aware receive handling and change-only scheduling

- **Objective/value:** prevent the application from fighting stock controls or claiming a stale frame is visible. High value; this is the main transport integration gap.
- **Confidence/effort:** high for need, medium for exact-unit runtime behavior; M.
- **Dependencies/environment/authority:** N2 contract; offline parser/state-machine work here, Windows build elsewhere; live behavior requires N5.
- **Observed implementation gap:** `ReadOneAck` accepts exactly one 10-byte ACK and rejects trailing/oversize data. `ExchangeSequenceOnce` sleeps between frames and closes after a precomputed sequence. It does not continuously observe unsolicited reports while idle. Do not drive M9 by repeatedly invoking `image-show` or reopening finite sequences.
- **Work:** extend the existing transport narrowly with bounded frame assembly and receive observation during the active session, including idle waits. Distinguish ACKs from exact-unit state reports; handle fragmented/coalesced input without assigning new command semantics. Retain validation, receive bounds and fail-closed behavior for unrecognized/malformed input.
- **Work:** observed unsolicited `0x46` invalidates the canvas and ends display sending; a late ACK cannot restore ownership. The M key also opened a stock menu with an unsolicited `0xBD` report: do not imply a `0x46` fence detects every takeover. Conservatively stop on an unexpected state report and qualify the menu case in N5 rather than infer broad `0xBD` semantics. No reclaim frame or “restore stock” command is sent on stop.
- **Work:** maintain desired/current state separately from last ACKed frame and last known canvas status. Coalesce to the newest image, compare rendered hashes, send only on change, and never replay queued pulses after interruption. Age/health transitions may legitimately change the image even without new activity. A short pulse should survive to a permitted display slot within its current freshness window, not be lost between polls or replayed much later.
- **Pacing:** retain the proven 1000 ms post-ACK delay and packet spacing; additionally prevent sustained frame starts faster than the accepted approximately 1118 ms interval. Do not mistake 1000 ms delay for a proven 1 fps rate. The ceiling is not a heartbeat: unchanged scenes send nothing. Any faster policy needs separate evidence and grant.
- **Exit:** fake-clock/transport cases cover unchanged state, burst coalescing, pulse expiry, idle takeover, ACK plus report in one read, fragmented reports, malformed input, late ACK, expiry, partial send and controller stop. On every ambiguous Bluetooth outcome, sending stops and collection remains available. No raw-send API or navigation events are introduced.

### N4 — Qualify sources and preview the real session offline

- **Objective/value:** establish that the finished display tells the truth before spending device time. High value, S.
- **Confidence:** high for fixtures and renderer; source accessibility remains environment-dependent.
- **Dependencies/environment/authority:** existing M9 plus N2/N3 interfaces. Fixtures/previews here; real source reads in a session with the necessary established access. These are read-only and do not need a device grant.
- **Work:** reuse adapters and their existing tests. Run a bounded scenario through collection, render, scheduler and fake transport: fresh activity, repeated unchanged state, source failure, recovery, restart seed and clock skew. Verify three sources independently in the capable environment; label generated test activity, do not call dispatch a completion or source readability service health.
- **Work:** review nearest-neighbor previews at realistic low-rate timing and confirm health remains legible. Retain unknown/unavailable states; do not hide an inaccessible source behind an idle color. Do not recreate cursors, deduplication, seeding or endpoint discovery already implemented.
- **Evidence closed:** actual source access in the deployment context; no-history replay; readable low-rate application frames. Lab completion semantics remain intentionally absent.
- **Exit:** reproducible fixture preview plus per-source reachability/meaning report, sanitized configuration example, zero fake sends while unchanged, and an explicit list of any real source still unavailable. Require real access to all three before calling the complete three-source product accepted; degraded-mode testing can proceed separately.

### N5 — First bounded M9 activation and stock-yield acceptance

- **Objective/value:** prove the actual activity app on the exact purchased unit. Highest immediate product value.
- **Confidence/effort:** medium; M including implementation/build review and short scheduled trials.
- **Dependencies/environment/authority:** N1–N4, offline PASS, Windows build/installed hash verification, reachable authenticated Host, functioning sources, operator available, other controller disconnected. **New manifest and explicit operator grant naming its experiment ID required for every live trial. This environment cannot perform the required Windows integration.**
- **Trial scope:** one short supervised session with exact lifetime and derived worst-case frame/packet/byte budgets; activity and health changes only at the accepted pace. Define these numeric budgets and frozen build hashes in the reviewable experiment artifact before requesting the grant. Prefer the smallest window that demonstrates change, idle silence and stop; no duration is authorized by this roadmap.
- **Evidence closed:** dynamic image acceptance and visual identity/color/health readability; receive behavior under our controller; stock-yield behavior. Test brightness/page takeover and menu takeover in separately scoped cases if the first stop ends the session. Each restarted connection requires its own new experiment/grant, not a retry within a consumed one.
- **Exit:** planned/actual bytes, packets, timing, ACKs and clean close are recorded; operator confirms display state transitions; no frame is sent after observed takeover; collection survives display stop; local status says stopped/unknown honestly. Any ambiguity is recorded and blocks promotion. A successful short trial does not authorize installation-time or unattended transmission.

## After that — make the app dependable and release it narrowly

### A1 — Install collection and controlled activation

- **Objective/value:** remove terminal babysitting without silently starting Bluetooth. High value, M.
- **Confidence:** high for standard process supervision, medium for sign-out/WSL lifecycle integration.
- **Dependencies/environment/authority:** N5 accepted; existing Windows at-logon Host retained. Worker/config/install scripts can be authored offline here; Windows/WSL installation and sign-out/restart acceptance need the capable environment. Collection-only installation needs no transmission grant; any display-start acceptance needs a new named grant.
- **Work:** one native supervised WSL worker using the existing collector, single-instance ownership, bounded logs, atomic cursor state, start/stop/status and uninstall. Startup runs collection only. Explicit session activation consumes a reviewed grant; expired/consumed authority stays disabled after login. Check ordering when Host or sources are late without retrying Bluetooth.
- **Evidence closed:** end-to-end startup and shutdown, including no duplicate worker and no accidental authority restoration.
- **Exit:** sign-out/login and restart restore collection once, preserve privacy and restart seeding, expose unavailable dependencies honestly, and produce zero Bluetooth operations absent a fresh grant. Uninstall removes the worker without touching OpenTivoo or private research evidence.

### A2 — Fault, recovery and longer-duration qualification

- **Objective/value:** turn short successful experiments into bounded everyday use. High value, M–L depending on findings.
- **Confidence:** medium. Existing twenty frames do not justify unattended durability claims.
- **Dependencies/environment/authority:** N5 and A1; fault fixtures offline; actual disconnect/power/controller cases and longer sessions require capable environment and new individually scoped grants.
- **Work:** test source timeout separately from device failure; then worker termination, Host termination, HTTP uncertainty, disconnect during send/ACK, device power loss, stock takeover, and competing-controller precheck failure. Simulate first. Physical trials should each answer a remaining question, not mechanically repeat every fixture on hardware.
- **Default recovery:** stop Bluetooth on fault, record completed and unknown bytes, preserve collection, release ownership and require operator recovery. Restart collection freely; never automatically reconnect or resend. Stock return is an operator action after recording the result, using documented exact-Ditoo controls. Do not import Tivoo double-power recovery behavior.
- **Durability:** add minimal bounded on-disk session receipts, because existing Host diagnostics retain only five operations in volatile memory. Preserve experiment/build/hash identity, timing, terminal state and unknown outcome; not tokens, raw logs or pixel payload histories. Do not grow an observability stack.
- **Longer use:** progress from supervised short trials to explicitly bounded longer sessions only after the preceding result passes. Measure frame changes/ACKs, resource growth, stop responsiveness and observed stock behavior. Prefer change-only traffic. A power-cycle return to clock does not prove flash-write absence; keep that limitation in the acceptance report.
- **Exit:** recovery matrix has measured/simulated/not-tested labels; no reconnect under any covered fault; duplicate activation fails; latest state alone appears after separately granted restart; a chosen finite operating envelope passes without unbounded memory/log growth. No “24/7 safe” claim from a short soak.

### A3 — Exact-unit release and operating guide

- **Objective/value:** make the accepted application reproducible and maintainable. High value, S–M.
- **Confidence:** high after A1/A2; no new protocol research needed.
- **Dependencies/environment/authority:** accepted build and finite operating envelope. Documentation, packaging and verifier work offline; Windows release build in capable environment. Packaging needs no grant; release acceptance involving a send does.
- **Work:** release notes and compatibility statement scoped to this Ditoo Plus on v42012 and tested Windows/WSL topology; committed source identity, build hash, dependency requirements and install/rollback instructions. Preserve port 8796/token/task separation from OpenTivoo 8779. Do not retrofit a multi-device framework.
- **Verification:** keep the existing artifact verifier and meaningful new authority/receive/lifecycle tests; add a separate Windows build gate and recorded physical acceptance. Distinguish source verified, build verified, installed verified and device accepted. Validate sanitized publication contents and ignore rules; raw captures/bugreports stay private and are never committed.
- **Docs:** concise quick start, source meaning/legend, activation/grant procedure, stop/recovery, stock takeover, unknown display state, diagnostics, uninstall and limitations. Rollback must restore collection without reviving a prior grant. Recheck Git status before committing only task-owned changes; do not stage unrelated work.
- **Exit:** a clean checkout can pass offline verification and produce the documented build; install/uninstall instructions have been exercised in the target environment; release evidence identifies its exact scope. Publishing beyond the requested deliverable remains a separate task.

## Later — earn expansion through use, not parity targets

### L1 — Product refinement or one additional local information view

- **Objective/value:** fix demonstrated daily-use friction; conditional value, not an obligatory feature backlog.
- **Confidence/effort:** high for a small renderer change, low that another app is presently needed; S–M only after a concrete need.
- **Dependencies/environment/authority:** A3 and actual use feedback. Offline design/rendering here; new physical acceptance needs a new manifest/grant even if the transport is unchanged.
- **Scope:** refine readability or intentionally import supplied artwork while preserving separate health/unknown semantics. If a second page is genuinely useful, select it locally using the smallest existing CLI/control surface. A compact source-detail or AI-usage view is a candidate, not a selected requirement. Do not build a web dashboard, plugin system or menu framework speculatively.
- **Capability closed:** an observed usability gap or a named second information need, not abstract Tivoo feature parity.
- **Exit:** owner identifies the problem, preview solves it, and the accepted device trial validates it within the existing rate/authority envelope. If no such problem emerges, **this axis has nothing further worth building**.

### L2 — Reconnection or unattended activation policy, only if demanded

- **Objective/value:** reduce manual recovery only if A2 records enough real interruptions to justify it. Potentially valuable, higher preservation risk and complexity.
- **Confidence/effort:** low–medium, L.
- **Dependencies/environment/authority:** A2 failure evidence, explicit owner request to expand policy, revised authority contract and new reviewed experiment/grant. Offline design is possible here; live qualification is not.
- **Default decision:** not part of the first release. Automatic reconnect can compete with the stock app and replay an ambiguous operation. Reboot must not resurrect authorization. A future finite policy would have to name triggers, expiry, connection budgets, ownership proof and exactly which post-interruption actions are permitted; no indefinite standing permission is inferred.
- **Capability closed/exit:** measurable recovery benefit under a narrowly accepted finite policy, with no ambiguous resend or stock contention. If this cannot be demonstrated, retain manual recovery; **there is nothing else to implement on this axis**.

### L3 — Targeted preservation research only when it changes a decision

- **Objective/value:** preserve useful knowledge and close a specific product/recovery blocker. Variable value; broad exploration is deliberately parked.
- **Confidence/effort:** high for preserving acquired artifacts; low for undocumented hardware paths, XS to open-ended.
- **Dependencies/environment/authority:** a named question and decision it affects. Existing artifact parsing is offline; new live observations need a new manifest and named grant under the current standing rule. Acquisition from external sources needs a suitably connected environment. No device entry or probing is authorized here.
- **Exit:** each revived thread produces an attributable artifact/finding or bounded negative result and a changed decision. Stop when it no longer affects the product or preservation goal.

| Research question | Decision now | Revival trigger and smallest useful evidence |
| --- | --- | --- |
| Does the activity session observe stock takeover while idle? | Essential; N3/N5 | Exact-unit receive/visual evidence under custom ownership. Do not rerun navigation research to answer it. |
| Does every stock takeover produce `0x46`? | Do not assume; cover known menu case conservatively | A missed takeover during acceptance justifies one focused observation; no broad command enumeration. |
| Ten-frame visual order and cyan/magenta rendition | Cheap closure during N5 | Attributed operator observation; no standalone replay for cosmetic bookkeeping. |
| `0x09`: volume level or key identity | Optional, low value; gates nothing | Only revive for a concrete volume-display requirement. A bounded stock observation requires the operator/grant procedure of this task; do not inherit the older note's “no new authority” wording. |
| ACK payload meaning | **Not worth pursuing** | Only if future evidence shows it is necessary to distinguish a real acceptance failure. Current validation must not treat it as a success constant. |
| Navigation via arrows/joystick or M7.4 receive window | Parked; negative result is complete in tested context | A specific needed navigation feature plus new evidence suggesting another context. Reports with stock side effects are not key events. |
| Faster pacing / animation / video | **Not worth pursuing for this status app** | Demonstrated latency/readability need that change-only updates cannot meet; then a separately scoped rate investigation. Official-app 148 ms floor is not permission. |
| Eliminate preambles / delta updates | **Not worth pursuing now** | Measured bandwidth/resource bottleneck with meaningful benefit. Saving a few bytes is insufficient reason to deviate from the proven transaction. |
| Nonvolatile side effects of repeated image display | Important limitation, not a reason to probe flash | A concrete wear/persistence concern or cheap exact-version static evidence; inspect retained artifacts first and retain version limits. Never claim no flash writes from a clock-after-reboot observation. |
| Installed v42012 firmware artifact / branch differences | Opportunistic preservation, not M9 blocker | A trustworthy exact-version artifact becomes available, or version-specific behavior obstructs a real goal. Hash/provenance first; no flashing. |
| MassBoot key mapping, GPIO role, USB/service mode | Parked, expensive and speculative relative to a working app | Loss of the supported application path or an explicit preservation need for a recovery/dump capability, plus a separately reviewed safe research plan. No guessed combinations or inherited Tivoo commands. |
| Firmware update path / historical support files / old APKs | Preserve existing leads; no active sprint | A specific recovery or compatibility question requires the missing artifact. Do not update firmware as a discovery technique. |
| Teardown / exact chip suffix / board revisions | **Not worth opening the working unit now** | A repair or hardware reuse objective that cannot be answered from existing imagery/artifacts and explicit owner authorization. |
| BLE alternative / alternate transport | No present value over proven Classic transport | Measured platform limitation prevents the intended product and justifies exact-unit transport characterization. |
| True per-tool Lab completion/counts | Optional, not a rendering bug | Owner needs completion semantics and established access to the VM audit exists. Current forwarded-command signal is honest and sufficient; do not change access controls for richer metrics. |

## Operating policies to preserve across every horizon

| Event | Display behavior | Collection and recovery |
| --- | --- | --- |
| Normal launch/login | No connection or send without a fresh valid grant | Collection may start; seed without pulses from old history. |
| State unchanged | No frame sent | Continue bounded polling and receive observation during an authorized session. |
| Source unreadable | Display unavailable/unknown if an active authorized session permits the changed frame | Other sources continue; source recovery is not Bluetooth reconnect. |
| Observed stock takeover | Stop sending, invalidate canvas, release session | Preserve collection; no automatic reclaim. |
| Send/ACK/HTTP outcome ambiguous | Stop/expire session; record unknown bytes or outcome | No resend/reconnect; operator records result before stock recovery. |
| Worker/Host crash or expiry | No continuation past Host-enforced bounds; authorization cannot revive | Restart collection only; new live attempt requires new manifest/grant. |
| Operator wants stock app | Explicitly stop and release OpenDitoo first | One controller at a time. |
| Device power cycle | Treat display state as unknown/stock per observation, not custom | Do not restore the last frame automatically. |

## Ordered execution sequence

1. **N1:** reconcile authority/current-state wording and evidence bookkeeping in a minimal documentation change.
2. **N2:** draft the bounded M9 session contract and implement durable one-use activation offline, leaving authority disabled.
3. **N3:** implement receive-aware stock yielding and change-only scheduling using the existing encoder/transport boundaries.
4. **N4:** run fixture-based session previews; verify real sources from a capable environment without device I/O.
5. Build and verify the exact Windows artifact in that environment; prepare the concrete N5 manifest and acceptance checklist. Only then request the operator's explicit grant naming the experiment ID.
6. **N5:** execute the granted bounded activation; record separate transport, visual, stock-yield and remaining-unknown results. Additional cases require fresh manifests/grants.
7. **A1:** install collection and controlled activation; prove restart/login causes no unauthorized transmission.
8. **A2:** qualify targeted faults and incrementally longer finite sessions; retain manual reconnect and durable receipts.
9. **A3:** package the exact-unit release with reproducible build identity, operating guide and scoped acceptance evidence.
10. Review actual usage before **L1/L2**. Revive an **L3** thread only if its trigger occurs; otherwise stop expanding the project.

**Single next action:** prepare a minimal offline documentation reconciliation patch for `AGENTS.md`, `START_HERE.md` and the current handoff, explicitly stating that every live operation—including static `image-show`—requires a new manifest and a named operator grant, and linking completed M7/M8 evidence instead of proposing it again. Preserve all consumed manifests and raw evidence. Then proceed directly to the disabled N2 activity-session contract; no device transmission is part of either action.

## Repository evidence index

All paths below are relative to `/home/wan/Projects/openditoo-research` at the inspected HEAD. These are repository sources, not web claims.

- `notes/OPENDITOO-HANDOFF-2026-09-09.md` — current accepted work, authority, operating ceiling and open questions.
- `AGENTS.md`, `START_HERE.md` — execution boundary and routing; contradictions identified above.
- `PROJECT_STATE.md` — inspected historical reconstruction sections; output was truncated, so this roadmap does not claim a full-file audit. Only explicitly observed deferred topics are used.
- `notes/OPENDITOO-M6-RUNTIME-ACCEPTANCE-2026-09-09.md` — installation, diagnostics, geometry and volatility, including nonvolatile-write caveat.
- `notes/OPENDITOO-M8-SEQUENCE-EVIDENCE-2026-09-09.md` — same-session choice, preambles, A/B visual result and historical scope.
- `experiments/DAY1-M8-FINITE-LOOP-002-RERUN.json` — consumed grant, reproducibility, actual budgets, timings and pending visual order. Other loop results are summarized by the handoff and this manifest; no new replay was attempted.
- `notes/OPENDITOO-M9-SOURCE-DISCOVERY-2026-09-09.md` — completed collectors, source semantics, renderer and existing verification.
- `captures/OPENDITOO-M7-KEY-SWEEP-2026-09-09.json` — exact-unit state reports, silent controls and derived-field/prose discrepancy.
- `host/activity_render.py` — current actual renderer and RGB888 output.
- `cli/openditoo.py` (`sequence_run`) — existing manifest checks, request body and result validation.
- `runtime/windows/OpenDitoo.Day1.Host/Program.cs` — typed capabilities and sequence route.
- `runtime/windows/OpenDitoo.Day1.Host/WindowsRfcommStaticImageTransport.cs` — ACK-only receive loop, inter-frame sleep, fixed session ownership and close behavior.
- Session verification: clean Git status; `DAY1_OFFLINE_PASS artifacts=19 tests=79`; three capability probes as recorded above. No private raw bugreport or btsnoop content was opened or copied into this deliverable.
