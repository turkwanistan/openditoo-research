# OpenDitoo streaming / next-objectives handoff — 2026-09-09

## Read this first

The live repository is authoritative over this note and all chat history. This handoff marks the end of MCP Dashboard v1 productization and the beginning of the next OpenDitoo phase: streaming and other owner-selected objectives.

At handoff creation, `main` is at `10c256c15f2e6944fbec3dc7e4cec0c5d43ba2e6`, the worktree is clean, and `python3 scripts/verify_day1_offline.py` passes **170 tests**. Re-check HEAD/status/verifier in your own session before acting because this exact hash will be superseded by the handoff commit itself.

## 1. MCP Dashboard v1 is CLOSED

Do not continue product-hardening it unless there is a concrete regression.

Accepted and frozen:

- exact Ditoo Plus `11:75:58:CE:DE:C7`, firmware `v42012`, RFCOMM channel 1;
- persistent MCP Dashboard v1 product runtime;
- Runtime 002 telemetry successor live under explicit standing grant `OPENDITOO-PRODUCT-RUNTIME-002` in the local git-ignored mode-0600 `.openditoo-local/product-runtime-policy.json`;
- Runtime 002 physical cutover PASS: `runtime_revision=2`, `status=connected`, session-open timestamp and ACK telemetry present, `last_error=null`;
- layout, real MCP activity animation, green/yellow/red/grey aging, simulated-source fault-bar visual path, initial attach, stock-screen reclaim, and device power-cycle reconnect accepted;
- P2/P3/P4 closed in `notes/OPENDITOO-MCP-DASHBOARD-V1-RELEASE-2026-09-09.md`;
- concise operator guide: `PRODUCT.md`.

Windows reboot/login autostart observation remains intentionally deferred/non-blocking. A forced genuine Lab outage was deliberately waived; do not create one merely to close evidence.

## 2. Authority boundary

Read `AGENTS.md` before any live operation.

- Activations 001–009 and all historical rate/sequence experiment grants are consumed.
- Runtime 002 standing product authority covers **only the existing MCP Dashboard v1 loop** and its accepted reconnect/reclaim behavior.
- It does **not** authorize a new streaming application, arbitrary image sequence, raw-send surface, target override, command enumeration, firmware/persistent writes, generic Bluetooth behavior, or pipelining.
- Any new live streaming trial must follow the repository's current experimental authority model: prepare a new reviewed manifest/experiment identity and receive an explicit operator grant naming it before transmission.
- Do not mutate the local Runtime 002 policy to smuggle new behavior into its standing scope.

## 3. Environment handoff

The next operator is local Claude running directly inside WSL and is expected to have more direct Windows/WSL integration than WSL_MCP. **Verify capabilities rather than inheriting them.** Cheap read-only checks from the existing handoff remain useful:

```sh
command -v powershell.exe
python3 cli/openditoo.py status
python3 cli/openditoo.py activity-probe
```

Also inspect the real Windows Host/build identity before any build-sensitive or live step. Preserve OpenTivoo completely; its runtime remains separately owned and port 8779 must not be disturbed. OpenDitoo Host remains on `127.0.0.1:8796`.

## 4. Proven streaming/rate baseline — do not repeat R1–R5

The rate ladder is complete and already physically accepted. Hydrate the exact evidence before planning new trials:

- `notes/OPENDITOO-HANDOFF-2026-09-09.md` — accepted operating ceiling and traps;
- rate experiment/result artifacts under `experiments/` / `notes/` as needed;
- `OPENDITOO-FORWARD-ROADMAP-2026-09-09.md` — historical roadmap, but its old statement that streaming is tabled is superseded by this handoff and owner direction.

Established exact-unit facts:

- R4 sustained full-colour repeated-frame path: **7.63 fps** over 512 frames / ~67 s with one ACK per frame and no degradation observed;
- R5 no-sleep ceiling: **18.46 fps** over 1024 frames / ~56 s, full colour, one ACK per frame, no tearing observed;
- the 18.46 fps result is the ceiling of the tested synchronous ACK-per-frame protocol shape, not necessarily the panel's physical maximum;
- full-colour payload size was not the limiting factor;
- short bursts overstate sustainable paced performance; do not repeat ten-frame ladder work;
- activity-product pacing at 150 ms Host floor / 200 ms nominal client cadence is a dashboard policy, not a streaming ceiling;
- pipelining/delta/partial-frame discovery remains prohibited unless a future separately reviewed objective justifies changing that boundary.

## 5. Next objective: streaming, then owner-selected applications

The immediate next session should **not blindly transmit**. First turn the existing R1–R5 transport knowledge into the smallest useful streaming implementation/acceptance plan.

Recommended first target: a bounded, exact-unit **general frame-streaming primitive/app path** that can feed precomputed or generated 16x16 RGB888 frames over the already-proven full-frame transaction while preserving one-controller ownership and existing typed transport boundaries.

Prioritize practical outcomes, not more protocol archaeology. Candidate objectives to evaluate/rank after hydration:

1. reusable local frame streaming API/CLI for arbitrary generated 16x16 frame sequences;
2. MP4/video -> 16x16 preprocessing + streamed playback;
3. live/generated visuals (procedural animation, camera/game/screen-derived frames) only after the generic bounded stream path is clean;
4. audio synchronization as a separate layer, not a reason to change the device protocol prematurely;
5. additional small everyday apps only if the owner names one.

The owner explicitly wants to move on from MCP dashboard hardening. Do not resurrect durability soak, firmware/MassBoot, ACK-byte decoding, teardown, command enumeration, alternate transport, or speculative UI work as prerequisites.

## 6. What the next session should produce

Hydrate selectively, then:

1. determine what streaming code/CLI/routes already exist versus what is missing;
2. compare the exact accepted R4/R5 transport shape with current typed Host/session/sequence implementations;
3. define the smallest forward architecture that reuses proven code rather than adding a second Bluetooth stack;
4. implement offline-safe pieces first with deterministic tests and no new transport escape hatches;
5. prepare a bounded first streaming acceptance manifest only when the implementation/build is reviewable;
6. stop before live transmission unless explicit authority for that new experiment exists;
7. keep routing/handoff/state updated and preserve legitimate concurrent/untracked work.

If the repo already contains a newer streaming plan or implementation when you hydrate, follow the live repo instead of this note.

## 7. Traps worth carrying forward

- One controller at a time is real; the official app can hold the link.
- Never interpret ACK payload bytes as a constant success value.
- ACK latency historically included our own packet-spacing sleeps; do not repeat that analysis mistake.
- Do not use fixed small response-read caps for long streaming result payloads; the CLI now bounds at 8 MB and detects truncation.
- Do not infer absence of nonvolatile writes from the stock clock returning after reboot.
- Do not re-arm consumed manifests. A new live attempt gets a new experiment ID and grant.
- Do not weaken exact-target/authority tests to make a new streaming feature convenient.
- Preserve OpenTivoo task/Host/port/state completely.

## 8. Canonical MCP-product references

- `PRODUCT.md`
- `notes/OPENDITOO-MCP-DASHBOARD-V1-RELEASE-2026-09-09.md`
- `notes/OPENDITOO-MCP-PRODUCT-BASELINE-FREEZE-2026-09-09.md`
- `product/OPENDITOO-PRODUCT-RUNTIME-002.json`
- `host/product_runtime_v2.py`

These are reference/baseline now, not the next implementation target.
