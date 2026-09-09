# OpenDitoo implementation plan: reliable runtime, physical inputs, repeated frames and MCP activity

Date: 2026-09-09  
Status: implementation/research plan; not a live-device experiment authorization  
Execution environment: local Claude in WSL, with Windows owning Bluetooth

## 1. Outcome and execution order

Deliver an OpenDitoo application that shows activity for **OptiPlex MCP, OptiPlex Lab and WSL MCP** on the Ditoo Plus's 16×16 screen. Poll their existing logs, normalize new activity and source health, and render three distinct indicators with activity animation and age-based color. Use physical controls for useful navigation only where exact-device evidence supports them.

Implement four milestones:

1. **M6 — Accept the deployed typed static runtime and make diagnostics truthful.**
2. **M7 — Map keyboard/buttons and establish whether usable inputs reach the host.**
3. **M8 — Prove a bounded repeated-frame/session primitive.**
4. **M9 — Ship the three-MCP activity application with reliable startup.**

These labels follow completed Day-1 M0–M5 but are proposed: use different identifiers if the live repository has already assigned them. M9 collector, state-model and preview work can proceed offline while M7/M8 await operator participation. M7's negative result must not block a useful application controlled locally. M8 does gate automatic physical display updates and animation.

Start M6 immediately. Do not restart M0–M5, rebuild the entire Tivoo stack, or make video parity a prerequisite.

## 2. Evidence baseline and mandatory reconciliation

The preceding planning session inspected these live repositories:

| Project | Snapshot | Observed result |
| --- | --- | --- |
| OpenDitoo | `main`, `42cd61893d085b8ea3fa0b20cc6e8a3a4c35c2fa`, clean | `DAY1_OFFLINE_PASS artifacts=19 tests=22 host=typed_image port=8796 device_io=false m4_completed=true m4_authorized=false m5_authorized=false` |
| OpenTivoo | `master`, `282d7da97aaa96b4ffe692f5802aa9ec1a4cb0e8`, existing modified/untracked work | FAST hydrate PASS; canonical D-358 accepted product; full TRUST not run |

These are provenance, not pins for future execution. Refresh Git status/HEAD and current routing before implementing. Never overwrite concurrent changes to restore these snapshots.

### OpenDitoo facts

- Exact purchased unit: Ditoo Plus, installed version v42012, target `11:75:58:CE:DE:C7`, measured Windows Classic RFCOMM channel 1.
- M5 attempt 2 visibly rendered the frozen custom diagnostic, received wrapped `0x44` ACK payload `0x12`, and closed cleanly. M5 authority is consumed.
- The typed runtime accepts an exact 16×16 PNG, deterministically decodes RGB888, builds a stock-derived image packet, and verifies Python/C# packet-hash agreement before Bluetooth I/O.
- PNG limits include 8-bit non-interlaced data, validated CRCs, deterministic alpha composition on black, and at most 255 distinct resulting colors.
- `image-show` is one connection, three packets, one image, one ACK and close, with no automatic retry or target/raw-packet override.
- A read-only authenticated probe of `127.0.0.1:8796` advertised `status` and `image-show`. Deployment is therefore further along than the post-M5 handoff's pending-deployment text.
- That probe does not establish installed-source identity, physical image acceptance, device connectivity or lifetime activity. `Program.cs` currently returns constant `bluetoothTouched=false` and `deviceIo=false` status values.
- The current Host has no continuously open receive window after image completion.

### OpenTivoo reference facts

- Accepted current product at inspection: D-358, Summary → Claude → Codex → Summary, with physical acceptance and earlier real reboot/sign-in durability proof.
- Input pagination derives from a measured display-takeover episode. `0x46` does not provide proven CW/CCW identity; its semantics must not migrate to Ditoo.
- Historical bounded animation/streaming and video-derived transport provide architecture references. TV static was physically observed in later trial work, but the newer TV stack is not the accepted D-358 baseline.
- Existing dirty/untracked TV, media and build work must be preserved and must not become an implicit dependency of OpenDitoo.

### Hydration procedure

For OpenDitoo, inspect status/HEAD, read `AGENTS.md` and `START_HERE.md`, run `python3 scripts/verify_day1_offline.py`, then follow the current post-M5/runtime route. Read `PROJECT_STATE.md` selectively: historical service-mode priorities are superseded by the application-first route.

For OpenTivoo, inspect status/HEAD, run `tools/venv/bin/python scripts/verify_cached.py fast --profile hydrate`, read `START_HERE.md` and current generated routing, then inspect `state/current.yaml`. Read only the reference implementation needed for the current milestone.

Record any newer completed work and remove already-satisfied tasks from this plan. A stale handoff is not justification to repeat a physical experiment.

## 3. Scope and architecture decisions

Keep Windows as the sole Bluetooth owner and preserve OpenDitoo's separate port, token, target, scheduled task and state. Do not replace or stop OpenTivoo.

For the application, prefer this minimal arrangement:

`three existing log sources → one WSL poller/normalizer → small activity snapshot → renderer → typed OpenDitoo Host → Ditoo`

Use the same normalized state for an offline/local preview. Use one polling process with a fixed three-source configuration, existing dependencies or Python's standard library, and bounded JSON state. Do not introduce a database, message broker, plugin framework, generic Bluetooth API or shared multi-device runtime.

A remote source adapter may read through existing authenticated access. Do not invent paths, endpoints, credentials or connectivity. If remote access is unavailable, implement against sanitized fixtures and report exactly what access is missing. Do not change MCP servers merely to make polling convenient until existing read paths have been evaluated.

Reuse pure Tivoo image/rendering utilities where useful, but retain Ditoo's RGB888 encoder and demonstrated palette limit. RGB222 may be an artistic palette choice; it is not a demonstrated Ditoo requirement.

## 4. M6 — Static runtime acceptance and diagnostics

**Value/confidence/effort:** high / high / small.  
**Closes:** deployed-code versus accepted-product gap; misleading status.  
**Execution classes:** offline implementation, Host-only inspection, explicit operator static-image acceptance.

### M6.1 Reconcile installation without unnecessary deployment

1. Inspect existing CLI, Host, installer, refresh script and post-M5 evidence.
2. Identify the installed executable and available build identity using existing Windows access. Local WSL may offer interop even though the earlier WSL_MCP sandbox did not; check rather than assume.
3. Compare installed identity with source and API capabilities. If the installed build already matches, do not refresh just to replay installation.
4. Update the runtime note to distinguish source implemented, build validated, installed, Host reachable and physical PNG acceptance. Record evidence for each independently.

### M6.2 Improve operation diagnostics in the existing Host

Extend the current status/transaction contract, preserving existing callers. Separate:

- Host readiness and advertised capabilities;
- whether the status request itself performs device I/O;
- whether a transaction is in progress;
- last operation ID, source image hash, start/end times and terminal result;
- last completed stage: validation, target precheck, connect, packet transmission, ACK, close;
- known application packets/bytes sent, with unknown/partial values represented honestly;
- last ACK and bounded failure code;
- device connectivity as unknown when no active observation establishes it.

Do not return a historical success as current connectivity. Do not expose bearer tokens, raw caller arguments or unrestricted packet APIs. Keep at most a bounded recent operation summary; a database is unnecessary. On restart, mark prior volatile observations unavailable or explicitly historical.

### M6.3 Verify encoder/CLI boundaries

Use existing tests and add focused cases for asymmetric orientation, alpha-on-black, supported palette inputs, excessive colors, malformed PNG and Python/C# hash mismatch before I/O. Validate the current contract's exact packet count and no-retry behavior. Mock transport for fault-stage tests; never use a live device in an offline verifier.

### M6.4 Accept the product path

Prepare `examples/openditoo-smile-16.png` offline and retain its hashes. Have the operator explicitly invoke the existing `image-show` primitive once when ready. Record returned hash/ACK and physical observation of orientation, marks and colors. If an existing exact acceptance is found, reference it instead of repeating the send.

An ambiguous result after transmission does not permit automatic repetition. Preserve the result and use the project's recovery boundary. A successful ACK alone is not visual acceptance or proof of absence of persistent effects.

### Exit criteria

- Installed identity and runtime state are reconciled with the repository.
- Status distinguishes Host health, past transaction evidence and unknown device state.
- Exact PNG → Host → device acceptance is recorded or clearly remains an operator gate.
- Existing static command behavior and offline verification pass.
- Documented startup/refresh instructions require no persistent user terminal for the Host.

**Tivoo reuse:** exact process ownership, structured status and installation lessons. Do not copy the full supervisor for a single Host.

## 5. M7 — Keyboard/button investigation and typed input model

**Value/confidence/effort:** very high / medium for characterization, unknown for remote key events / medium.  
**Closes:** usable physical navigation and action input.  
**Dependencies:** operator, attribution-quality capture, controller ownership. M6 diagnostics help but offline evidence review can begin independently.

### M7.1 Build an exact-unit control inventory

Use current photos/manuals or request one front/top photo if the labels cannot be established. Give each control a stable position-based inventory ID plus its visible symbol. Do not invent physical labels from firmware IDs.

Record known manual effects: power short press shows battery, power double press disconnects Bluetooth, hold power changes power state, and holding M changes keyboard backlight during normal operation. These are side effects to distinguish, not default input gestures to run.

Inspect existing stock captures and normal application input-dispatch evidence. Reference firmware's seven-position analog ladder is a lead; installed v42012 byte identity is unavailable. Do not pursue boot-time key selectors, test mode, MassBoot, teardown or speculative command enumeration.

### M7.2 Stock observation and attributable capture

Use one controller at a time. Begin with the official app and its already-proven capture workflow. Record context: stock page, app page, audio playback/profile state, firmware evidence, controller and connection identity.

For each trial, retain timestamped operator video or event markers, raw capture hash, filtered TX/RX with direction/profile/channel, before/after stock state and continuity/gap metadata. Keep raw captures private and immutable; commit sanitized derivatives and provenance only.

| Trial | Action | Expected observation to investigate | How it advances the model |
| --- | --- | --- | --- |
| B0 | No action for 10 seconds | Background telemetry, app queries, spontaneous state changes | Establishes baseline noise |
| K1 | One short press/release of one non-power control | Display, audio, lighting, app or Bluetooth change | Candidate control correlation |
| K2 | Repeat the same press in three isolated windows | Same code/report and side effect | Tests repeatability |
| K3 | Same control in one other recorded stock context | Identical or context-dependent behavior | Establishes mapping scope |
| K4 | Short press of an apparently inert control | Non-display effects or remote event despite unchanged page | Finds useful low-side-effect candidates |
| K5 | One bounded hold/release after short-press characterization | Press/release distinction, repeat cadence or long-press event | Determines which gestures are actually observable |
| K6 | Two separated presses, then a shorter measured gap | Two events, coalescing, duplicate telemetry or lost actions | Sets conservative software debounce behavior |
| K7 | One specifically justified pair while normally running | Chord, suppression, priority or separate events | Tests a supported combination hypothesis |
| K8 | Same proven short press during authorized custom-owner receive observation | Event survives without official app | Establishes custom Host feasibility |

Repeat baseline around action blocks. Restore stock state between trials and exclude restoration traffic. Choose hold duration and eligible keys from the manual and observed behavior; do not blindly hold every control. No power double-press or boot combinations in the normal key sweep.

### M7.3 Correlate offline before adding transport

Classify each result as raw-key-like event, absolute stock-state report, app-originated reaction, unrelated telemetry, no event observed or invalid observation window. Preserve unknown payloads.

Inspect other already-captured Bluetooth profiles when channel 1 is silent. A media-control event may travel on a different established profile; do not invent a BLE/HID endpoint or begin discovery merely because a key is silent. Any new protocol path needs an independently scoped investigation.

No event observed is not proof of internal-only handling. Report tested context, duration, capture completeness and paths observed. A lack of visible page change is not proof of no side effect.

### M7.4 Receive-window decision

The existing image transaction closes its socket. Do not quietly turn it into a persistent connection for key capture.

If evidence supports a custom-owner receive test, prepare a manifest specifying target/firmware, proven channel, connection count, duration, application TX budget (zero unless separately justified), RX bounds, one controller, stop conditions and no automatic reconnect. Even a receive-only connection is active transport behavior. Run only under explicit authority covering that experiment.

Keep one receive/parser owner. Input observation must not consume ACKs intended for display transactions; route validated packets by demonstrated semantics inside that owner.

### M7.5 Implement only demonstrated semantics

An input record should carry source/connection epoch, sequence or cursor, timestamp, observed event kind, value/identity if proven and interpretation confidence. Do not fabricate press/release from a state report. Clear pending gestures on gaps or epoch changes.

Start by driving a local counter or offline page preview. Add next/previous/select/back/home only when reliable distinctions exist. One usable next-page event is enough for the MCP display. Approval actions are deferred until deliberate activation, duplicate suppression and stale-event rejection are demonstrated; no external action should be triggered by experimental key mapping.

### Exit criteria

- Every inventoried control has a recorded tested/not-tested status, context, event result and side effects.
- At least one reusable mapping is proven, or a bounded negative result identifies the unavailable path.
- Offline replay reproduces accepted classifications and rejects gaps/duplicates appropriately.
- The result says exactly which application actions are supported and which remain unknown.

**Tivoo references:** `host/tivoo_input_events.py`, `TivooInputReceiveTelemetry.cs`, `TivooInputEvents.cs`, D-357 isolated mapping result. Reuse observation discipline and epoch/gap concepts, never Ditoo command assignments.

## 6. M8 — Bounded repeated-frame/session primitive

**Value/confidence/effort:** high / medium / medium.  
**Closes:** automatic updates and animation.  
**Dependencies:** accepted static primitive, stock sequence evidence, separately bounded live authority.

### M8.1 Choose a sequence from evidence

Inspect successive stock Pixel Coloring operations for preambles, ACKs, connection lifetime and frame format. Determine whether the least-change supported path is repeated complete transactions or a same-session sequence. Do not remove entry packets or adopt Tivoo deltas simply to improve speed.

Freeze a tiny asymmetric A→B sequence with deterministic source/frame/packet hashes and exact packet, byte, duration and connection ceilings. Include expected ACK handling, stop behavior, ownership, possible storage effects and no-retry policy. Avoid claiming a repeated operation is volatile merely because the single-frame test appeared temporary.

### M8.2 Implement offline state handling

Retain a single Host transport owner. Add the smallest typed operation needed for the reviewed sequence. States should distinguish closed/ready, applying, completed, stopping and faulted; use existing code rather than adding a framework. Validate input before I/O and make cancellation stop future work without claiming already-sent bytes were undone.

Use mock transport to test partial sends, unexpected ACKs, timeouts, cancellation, concurrent rejection and fault latching. A pending frame is not evidence of a displayed frame.

### M8.3 Live progression

1. Execute only the frozen A→B sequence after authority exists; capture visible order and ACK timing.
2. If successful, design a short, low-rate finite loop with a new explicit budget.
3. Measure actual inter-frame timing, ACK latency, errors and stock takeover. Increase rate only to satisfy the application, not to chase Tivoo's throughput.
4. Record the accepted operating ceiling and conditions. Translate that ceiling into the application's redraw/pulse budget.

### M8.4 Product-capable pacing

One component owns pacing. Keep a bounded pending frame slot/latest-state policy instead of a growing queue. Deduplicate identical frames only while canvas/session validity is established; after uncertain ownership, an old hash cannot prove the device still displays that frame. Do not reconnect or replay after ambiguity without the separately justified recovery contract.

A finite test is not standing authority for indefinite display. Before M9 activation, define the application's permitted automatic updates, lifetime/rate bounds, source of activation and fault behavior under the current repo rules.

### Exit criteria

- Ordered repeated frames are physically observed and matched to recorded transactions.
- The accepted rate, packet/byte cost, session behavior and state-effect confidence are documented.
- Stop/cancel and ambiguous failures prevent uncontrolled further sends.
- Host input observation, if supported, coexists with the same transport owner.

**Tivoo references:** `VolatileFrameSessionCoordinator.cs`, `WindowsRfcommVolatileCanvasSession.cs`, `host/tivoo_session.py`, historical bounded stream results. Reuse pacing/state concepts; reimplement Ditoo wire and persistence semantics.

## 7. M9 — Three-MCP activity application

**Value/confidence/effort:** high / high for offline model, conditional for physical product / medium.  
**Closes:** first useful everyday application, asset/UI workflow, startup and observability.  
**Dependencies:** actual source access; M8 for physical automatic updates; M7 only for physical navigation.

### M9.1 Discover the three sources

Inventory OptiPlex MCP, OptiPlex Lab and WSL MCP independently. For each, record:

- authoritative audit/log location or existing read endpoint;
- access method available to local Claude and the background WSL user;
- event schema, timestamp timezone/precision, stable IDs or cursor support;
- whether records represent request start, request completion, transport traffic or something else;
- whether failed calls appear and how long-running calls are represented;
- rotation/truncation behavior, retention and maximum practical poll size;
- available independent server/collector health evidence;
- whether the polling operation itself creates audit entries and how it can be attributed.

Read only enough sanitized examples to implement adapters. Do not load entire audit histories. Paths/endpoints for the three sources are intentionally unresolved in this plan. WSL_MCP exposes an audit-tail tool in this ChatGPT environment, but that does not guarantee an equivalent local Claude API or background-service credential path.

Prefer direct bounded log reads or existing read-only endpoints. A new exporter on OptiPlex is a fallback, not an automatic architectural requirement. Do not assume the two OptiPlex MCPs share a log or are independently reachable just because they share a machine.

### M9.2 Define honest activity semantics

The display represents **observed logged MCP activity**, not network packets, unless actual packet-level evidence is supplied. If only completion records exist, the pulse means newly observed completed activity; do not label a call in flight from silence.

Count failed MCP operations as activity while tracking their outcome separately. Exclude this application's polling, health probes and display maintenance using attributable collector identity/request ID/operation metadata. Do not blanket-exclude all status/log commands, since genuine user calls may use them.

Feedback-loop acceptance is mandatory: with no user activity, polling must not keep any icon active. If self-generated records cannot be attributed, switch to a non-audited bounded read path or explicitly resolve the limitation before claiming accurate activity.

Suggested initial timing defaults, to be tuned after measuring source cost:

- Poll each source every 2 seconds, with a per-source timeout shorter than the interval and no overlapping polls.
- Isolate sources so one slow endpoint does not delay the other two.
- Retry read-only collection with capped backoff; this does not permit retrying device sends.
- Mark observation stale after roughly three missed normal polls; show the collection error separately.
- Use a short activity pulse only for newly seen qualifying records, coalescing bursts rather than replaying hundreds of flashes.

These are proposed application defaults, not measured device rates or final UI acceptance.

### M9.3 Minimal normalized state

Keep one record per stable ID: `optiplex_mcp`, `optiplex_lab`, `wsl_mcp`.

| Field | Meaning |
| --- | --- |
| `last_activity_at` | Source event time of most recent qualifying activity, nullable |
| `last_observed_at` | Local time of most recent successful source read |
| `source_health` | Observed healthy, stale, unavailable or unknown; explicit meaning per adapter |
| `last_outcome` | Success/failure/unknown for latest qualifying event |
| `cursor` | Adapter-specific stable resume point with source generation identity |
| `new_activity_sequence` | Local monotonic sequence for pulse triggering |
| `history_complete` | Whether the collector knows the relevant tail was complete |
| `error_code` | Bounded sanitized collection error, nullable |

Separate log accessibility from MCP service connectivity. A readable local log does not prove the service is connected; a failed read does not prove the service is down. Use “unavailable/no data” unless independent health evidence supports “disconnected.” Keep the exact explanation in CLI/local preview.

Handle timestamp skew explicitly. Normalize source timestamps to UTC; reject or flag materially future timestamps instead of inventing zero-age activity. Use monotonic local time for pulse duration and scheduling. On restart, age persisted activity correctly and do not pulse historical records.

### M9.4 Incremental reading and state persistence

For files, use a cursor with generation/inode or equivalent identity plus offset; detect truncation/rotation. Buffer an incomplete final line and continue later. Bound bytes/records per poll, retain cursor when catching up, and expose a gap when retention has removed unread data.

For a bounded tail API, deduplicate by stable ID when available. If only timestamp/content fingerprints exist, document collision/retention limits and avoid claiming complete counts. Parse failures must not prevent valid subsequent records from being handled.

At first start, establish current last activity from a bounded tail but do not animate old events. If the tail cannot establish history, use unknown rather than idle. On resume, identify unseen events without double counting.

Persist only cursors, compact normalized state and version metadata atomically under OpenDitoo's local state directory. Keep tokens, arguments, command bodies, usernames and raw logs out of display snapshots. Use existing secure credential storage and do not commit local config/secrets.

### M9.5 16×16 interface and assets

The product has three fixed, distinct MCP indicators. Show stable identity, last-activity age and a transient newly-observed-activity signal. Icons must not touch; reserve explicit black separation and keep activity pixels inside each icon's allocated region.

Suggested age categories consistent with the requested interface:

| State | Classification | Rendering intent |
| --- | --- | --- |
| New activity | New qualifying record since the previous observation | Short pulse/animation, coalesced per poll |
| Recent | Known activity age <5 minutes | Strong recent-activity color |
| Warm | Age ≥5 and <20 minutes | Distinct intermediate color |
| Idle | Age ≥20 minutes with sufficient valid history | Dim neutral/idle treatment |
| No data | No reliable activity history | Explicit unknown pattern |
| Source stale/unavailable | Collection freshness failed | Distinct fault/uncertainty marker; retain last known age in detail |

Use age and health as separate state dimensions. A historical recent event must not hide a currently unavailable collector. Reserve red/error treatment for a defined error state rather than using it ambiguously for elapsed time.

Resolve any existing MCP UI mockups or approved assets from the live project/user-provided files before redesigning. This plan does not freeze an unseen prior icon sheet. If unavailable, create a small set of hand-authored exact 16×16 previews for review. No image generation. Store logical pixels directly; use nearest-neighbor PNG enlargement and GIF previews for animation QA. Validate dimensions, palette count, region separation and all health/age combinations.

Do not place text labels on the 16×16 summary unless they remain legible. A local preview should label all three sources and explain the legend. Optional device detail pages may show source identity and coarse age, only after a useful compact design is verified.

Polling and device animation are separate cadences. A short signal animation may run only within M8's proven rate and M9's authority. When the display is unchanged and no pulse is active, avoid unnecessary physical frames. If animation is too expensive, ship a static activity highlight that expires on the next permitted update.

### M9.6 Controls and local control surface

Minimum v1: summary screen plus a local status/preview command. A simple existing local web preview can be extended if available; a new large frontend is unnecessary. If adding a browser surface, bind locally and keep Host tokens out of browser code.

If M7 yields one safe event, cycle Summary → OptiPlex MCP → OptiPlex Lab → WSL MCP → Summary. With reliable separate actions, add back/select only where useful. Do not map keys to log deletion, server restarts, shell execution or approvals in v1. If keys have disruptive stock side effects, keep local navigation and document the limitation.

Expose structured CLI status with deterministic exit behavior following the repository's conventions. Suggested command concepts—not mandated filenames/subcommands—are activity status, offline preview, worker start/stop and source diagnostics. Keep collection health distinct from device/render health.

### M9.7 Startup and bounded recovery

Install the one WSL activity worker using the existing project's service/bootstrap pattern, with OpenDitoo-specific ownership. Start it at login alongside the existing Host without a persistent terminal. Validate noninteractive paths, credentials and remote log access; interactive-shell success is insufficient.

Polling may recover independently when sources return. Bluetooth faults stop further display operations until the exact product recovery policy permits recovery. Never replay queued activity animations after reconnection; show the latest normalized state. Preserve healthy OpenTivoo processes throughout installation and refresh.

After authorized activation, perform one planned sign-in/restart acceptance: collector starts, all configured sources report honest status, Host starts, display resumes within its approved lifecycle, and no terminal is required. If automatic device reconnection is not yet authorized/proven, explicitly scope the release to automatic collection plus operator display activation rather than claiming full plug-and-play.

### M9 acceptance matrix

| Case | Required outcome |
| --- | --- |
| One genuine call on each MCP | Only the corresponding indicator pulses, within measured poll/render latency |
| Failed genuine call | Counts as activity; outcome remains inspectable |
| Polling only, no user calls | No artificial perpetual activity |
| Boundary ages 5 and 20 minutes | Deterministic category transitions using a controlled clock |
| Duplicate records/restart | No duplicate pulses or replay of historical events |
| Log rotation/truncation | Resume safely or explicitly report a gap |
| Partial/malformed line | No crash; preserve enough cursor state to continue |
| Burst exceeding one poll budget | Bounded work and honest catch-up/gap state |
| One unreachable source | Other two continue; inaccessible source is not mislabeled idle |
| Readable log, service health unknown | No false connected claim |
| Clock skew/future timestamp | Explicit unknown/skew handling, no invented recency |
| Device fault | Collector continues; display stops under its fault policy |
| Source returns | Current state recovers without stale pulse replay |
| Worker/Host restart | State ages correctly, ownership preserved, secrets absent |

Exit when the three real sources are integrated, replay tests pass, UI is physically legible, no feedback loop exists, and daily startup behavior matches the documented release scope.

## 8. File organization and verification

Extend existing CLI, Host and tests first. Suggested additions are a small activity module, a renderer, sanitized fixtures, one operator input worksheet and one milestone result note. Match existing repository conventions; do not create these exact paths if equivalents exist.

Keep code/evidence in the OpenDitoo repository. Keep raw captures, credentials, cursor state and runtime output in the project's existing ignored/private locations. Record artifact hashes and sanitized provenance. Do not copy the OpenTivoo repository or couple Ditoo at runtime to dirty Tivoo source files.

Use focused tests for each milestone and the required OpenDitoo offline verifier. Device I/O must remain absent from offline tests. Use actual failure fixtures where available rather than tests that merely restate implementation details. Run the appropriate Windows compile/build checks before deployment. Do not repeatedly run OpenTivoo's full TRUST suite for unrelated Ditoo edits.

At each completed milestone, update current routing, readiness, result evidence, outstanding gates and exact next action. Preserve historical captures and failed attempts. Follow live repository commit/push instructions and stage only owned work; this plan does not authorize publishing unrelated changes.

## 9. Execution boundaries and stop conditions

Repository/offline work, log-adapter implementation, sanitized log reads and previews do not authorize Ditoo transmissions. Existing operator `image-show` permission remains limited to its explicit invocation. M7 custom receive sessions, M8 sequences and M9 continuous operation each require current authority covering their exact behavior.

Before a new live operation, prepare a concrete reviewed boundary with exact target/firmware evidence, deterministic application bytes where applicable, packet/byte/connection/time budgets, expected observations, persistence analysis, one-owner rule, stop/recovery policy and retry policy. Do all available offline preparation first.

Stop the affected live operation on unexpected target identity, conflicting owner, source-binding mismatch, unexpected protocol response, ambiguous post-send failure, unaccounted capture gap or state effects outside the experiment. Continue independent offline work where useful. Do not use guessed recovery commands, teardown, firmware updates, service mode, arbitrary sends or credential workarounds.

## 10. Next-session scope and handoff

First session: reconcile live state; finish M6's offline diagnostics/build/evidence work; identify any remaining operator static acceptance; prepare M7's inventory and capture worksheet. If blocked on operator participation, proceed with M9 source discovery and offline adapters/preview. Do not silently widen into M8 live work.

End each session with completed work, exact checks/results, repository state, remaining operator actions and the next executable step. Keep the requested action concrete, short and attributable. The objective is a working MCP activity product, not perpetual planning.

## 11. Local Claude orchestration/executor prompt

Use this plan to take over OpenDitoo implementation from local Claude in WSL. The live repositories outrank the plan and chat history.

Work in `~/Projects/openditoo-research`; use `~/Projects/opentivoo-research` selectively as reference. Inspect Git HEAD/status and preserve concurrent/untracked work. Read OpenDitoo `AGENTS.md` and `START_HERE.md`, run `python3 scripts/verify_day1_offline.py`, and follow current runtime routing. For Tivoo references, run `tools/venv/bin/python scripts/verify_cached.py fast --profile hydrate`, then inspect current routing and `state/current.yaml`.

Implement the plan in order: M6 static-runtime acceptance/diagnostics; M7 keyboard/button mapping; M8 bounded repeated frames; M9 the 16×16 activity interface polling OptiPlex MCP, OptiPlex Lab and WSL MCP logs. Reconcile newer completed work before repeating anything. Start M6 now. Prepare M7's operator worksheet, and advance M9's offline source discovery/adapters/preview when operator-dependent work is blocked.

Discover actual log paths, schemas and access methods. Distinguish logged activity, source freshness and device health; exclude the collector's own traffic; handle cursors, rotation, duplicates and clock skew. Reuse available UI assets and minimal existing architecture. No image generation. Keep the three icons separated and show activity pulses, age categories and honest unknown/unavailable states.

Implement and verify authorized offline work; do not stop at another plan. Preserve OpenTivoo's runtime and Ditoo's separate Host ownership. Do not inherit Tivoo protocol semantics or permissions. This prompt grants no new live-device authority: use only operations explicitly covered by current repository/session authority, prepare concrete bounded experiments before requesting operator action, and never auto-retry an ambiguous send.

Update repository routing/evidence as milestones complete, follow its Git workflow, and finish with changes, verification results, remaining gates and the exact next action.
