# OpenDitoo full-input takeover research — 2026-09-11

## Status

Research only. No device I/O, firmware write, TF-card update attempt, MassBoot entry, teardown, or standing-runtime change was performed.

Current product truth is Runtime 018; see `notes/OPENDITOO-HANDOFF-2026-09-12-R018.md`. This research note does not grant any device authority.

## Question

Can OpenDitoo make the Ditoo Plus front-panel controls belong to OpenDitoo while it is active, so pressing M / + / lighting / Left / - / Right / lever produces OpenDitoo input without first performing the stock firmware action?

Desired constraint: software-first / no soldering if possible.

## Executive conclusion

**Yes: there is now a credible software-only engineering path to exclusive OpenDitoo ownership of the front-panel controls.** It is not a Windows-only interception problem. A true takeover requires an in-device firmware or volatile-runtime hook that consumes key events before the stock Ditoo application handles them.

The strongest route is now:

1. identify the earliest common Ditoo key/event dispatch seam in exact-model firmware;
2. patch it so a bounded `OpenDitoo input claim` diverts keys to the existing Bluetooth control channel and returns before stock handlers run;
3. leave stock behavior unchanged whenever the claim is absent/expired;
4. deliver the patch through the Ditoo Plus's **real TF/SD firmware-update path** if the remaining operational/rollback questions are closed.

The hard part has shifted from **"can the firmware be patched to own the keys?"** toward **"can we make first installation and rollback acceptably safe on the owner's v42012 unit?"**

Confidence: **moderate-high that the input hook is technically feasible; moderate that the TF path can deliver it safely today; low that a host-only solution can ever provide true suppression.**

## 1. Why the current host-only path cannot solve this completely

Current exact-unit captures are already sufficient to distinguish two problems:

- **observe the input**;
- **prevent the stock action**.

Left/Right/lever are convenient because the Ditoo emits AVRCP pass-through events that Windows exposes via SMTC, so ButtonProbe can observe them. Some presses also produce proprietary RFCOMM reports (`0x09`, `0xBD`); the current Runtime 018 product retains the accepted canvas invalidation/reclaim behavior while using raw AVRCP as authoritative input.

The other controls visibly mutate stock state first (menu, volume, lighting/brightness). Even if every such mutation can be inferred from unsolicited RFCOMM state reports, Windows is downstream of the decision: it cannot make the stock handler un-run.

Therefore a true exclusive-input mode needs an interception point **inside the Ditoo** before normal stock dispatch.

## 2. Exact Ditoo Plus firmware has a centralized key/event architecture

Static analysis in this research pass used the preserved exact-model flag-42 v42016 image:

- file: `artifacts/firmware/flag42_v42016.bin`
- size: 1,207,313 bytes
- SHA-1: `4371b90f4a0846fbb8dc26b77ad03695962f7ffb`
- SHA-256: `f2509588d3ca52175591925298cdcffe9c7e01f6d43d89ee352b967610025b6a`

This is exact **Ditoo Plus family/model firmware**, but it is newer than the owner's installed v42012 and is not byte-identical purchased-unit firmware.

### Analog-key configuration

The board configuration block contains a `key` configuration with seven calibrated analog ranges / key IDs. This corroborates the existing project conclusion that Ditoo Plus uses a resistor-ladder analog-key subsystem rather than seven unrelated application actions.

The firmware separately contains power/wakeup paths such as:

- `wakeup by analog keypad!`
- `wakeup by power key!`
- `POWER OFF KEY PRESS!`

So the side power button should be treated separately from the ordinary front-panel takeover problem.

### Key events are software messages

The application contains multiple compact key/event dispatchers rather than each feature polling hardware independently. Examples from the exact binary include:

- `divoom_disp_game_key_function`
- `divoom_disp_game_app_key`
- `[key]NEXT`
- `[key]PREV`
- `[key]app press %d`
- `[key]bt press %d`
- `[key]OK:`
- `divoom_product_test_key_update`

The game-key dispatcher receives a key argument and routes it through a mode-specific jump table. Audio/Bluetooth-player dispatchers receive small event records and branch on event codes including the already-observed previous/next events.

The factory/product-test path is particularly useful evidence: its key-test routine compares incoming software event codes and advances a bounded key-test state machine. That means physical-key identity has already been transformed into software-level events before feature-specific behavior.

**Implication:** a small consume-or-forward hook is plausible. We should not need seven unrelated patches.

### What is not yet proven

We have not yet pinned the *single earliest normal-runtime producer/dispatcher* that is guaranteed to see every desired front-panel event before all stock consumers. That is the main static-analysis task for the next research milestone.

## 3. The Ditoo Plus TF/SD firmware path is real

This was the most important new finding of the pass.

The exact Ditoo Plus firmware contains UTF-16 paths:

- `divoom/divoomupdate.bin`
- `divoom/alarm.bin`
- `divoom/movie.bin`
- `divoomtest.bin`

Earlier project state correctly treated this as a firmware-update lead, but the important question was whether `divoomupdate.bin` genuinely came from removable TF/SD storage or merely from an internal filesystem namespace.

### Resolved: medium 0 is SD on this Anyka build

The exact filesystem wrapper used by the updater was disassembled. When called with medium ID `0`, it explicitly invokes the routine associated with the diagnostic string:

`Error: Fwl_MountSD fail!`

The same wrapper rejects nonzero IDs for this path. `divoom_check_update` uses medium ID `0` when it resolves and opens `divoom/divoomupdate.bin`.

Therefore, on **this Ditoo Plus / Anyka firmware**, the update checker is genuinely using the SD/TF filesystem.

This differs from the 2026 MiniToo work, where a similarly named path was shown to read a different medium. Do not transfer that MiniToo conclusion to Ditoo Plus.

### The exact updater validates the normal Divoom container

The `divoom_check_update` routine:

- opens the update path;
- reads the trailer/header material;
- checks the `DIVOOMUPDATE` marker;
- checks version-related fields;
- reads the update body in bounded chunks;
- computes an additive byte total and compares it with the stored value;
- logs `divoom_check_update: start update!` on the accepted path;
- feeds chunks into the existing update writer.

The preserved v42016 binary independently verifies the container arithmetic:

- trailer version: `42016`
- marker: `DIVOOMUPDATE`
- stored checksum: `0x06ab2183`
- `sum(all bytes except final u32) mod 2^32 = 0x06ab2183`

No cryptographic signature/HMAC/public-key verification was observed in this exact update-check path. The practical integrity gate traced here is version/marker/additive checksum.

### Independent field corroboration

A 2022 Ditoo Plus owner reported that Divoom support directly emailed a file named `divoomupdate.bin` and instructed them to put it on an SD card; support said the device would update and shut down. The user was unable to make their particular attempt trigger, so this is corroboration of the intended delivery mechanism, **not** proof that arbitrary cards/layouts/files always trigger correctly.

Source: https://www.reddit.com/r/Divoom_Products/comments/xt9r45

## 4. Public 2026 Divoom firmware-patching precedent

The separate `antiali.as/minitoo-forth` project is not Ditoo Plus evidence: MiniToo uses an Actions ATS2831, not the Ditoo Plus Anyka 1052D family.

It is nevertheless useful methodology evidence. That project independently demonstrated that another Divoom firmware family uses the same `DIVOOMUPDATE` + additive-u32 model, built a patcher that places code in a cave and replaces one dispatcher branch, and proved its injected FORTH kernel end-to-end in simulation.

Important counterexample: MiniToo's own software flash-delivery routes are currently blocked; its SD-looking update path was specifically disproven for that device. This makes the exact Ditoo Plus `Fwl_MountSD` result above important rather than something to infer from the filename.

Sources:

- https://tangled.org/antiali.as/minitoo-forth
- https://tangled.org/antiali.as/minitoo-forth/blob/public/docs/flash-delivery.md

## 5. OpenTivoo prior art: useful fallback, not transferable authority

OpenTivoo established on the related Anyka/Divoom family that MassBoot can provide volatile RAM read/write/GOTO-style execution and can be used to stage helper code without immediately flashing a custom application.

That makes a **volatile input hook** a credible fallback architecture for Ditoo Plus if its own MassBoot path can be safely entered and independently mapped.

But Ditoo Plus currently lacks exact proof of:

- the physical MassBoot key sequence;
- its service USB identity;
- command IDs;
- memory map;
- whether OpenTivoo's loader behavior is compatible.

None of those transfer automatically from Tivoo. MassBoot is therefore route B, not the primary route today.

## 6. Recommended product design: an explicit OpenDitoo input claim

Do **not** permanently delete stock key behavior. Make the patch fail-open to the vendor firmware.

Conceptual behavior:

```text
physical key/lever event
        |
        v
existing Ditoo key decode / event producer
        |
        v
OpenDitoo input shim
        |
        +-- claim inactive/expired --> existing stock dispatcher unchanged
        |
        +-- claim active ----------> emit typed input event to OpenDitoo
                                     consume event
                                     DO NOT call stock action
```

### Claim semantics

The device should only suppress stock input while a live OpenDitoo controller has explicitly claimed it.

Recommended rules:

- claim is activated through a new narrowly typed command on the existing OpenDitoo control connection;
- claim has a short TTL/heartbeat and automatically expires if Windows/WSL/OpenDitoo dies;
- disconnect immediately releases the claim;
- on release, all buttons revert to factory behavior without reboot;
- no second Bluetooth controller;
- key events are returned as a tiny typed record (`key_id`, edge/action class, optional hold state/sequence);
- no raw arbitrary memory/write interface is exposed as part of the product feature;
- preserve an emergency local escape.

### Power button

Do not make power-hold an OpenDitoo-only key. When the device is off there is no OpenDitoo runtime to own input, and a hard local power/recovery path is valuable.

Reasonable eventual behavior while powered on:

- six keyboard buttons + lever: claimable by OpenDitoo;
- power hold: always stock power-off/recovery;
- power short/double: only consider interception later, after the ordinary input path is proven and only if there is a compelling product use.

## 7. Best implementation routes, ranked

### Route A — patched Ditoo firmware via TF/SD update

**Most promising.**

Why:

- exact Ditoo Plus has a real removable-SD update path;
- exact updater checks the standard `DIVOOMUPDATE` container and additive checksum;
- input handling is already software/event based;
- patch can be small and fail-open;
- no soldering should be required for normal installation if the operational trigger is proven.

Main blockers before attempting it on the owner's unit:

1. purchased unit is v42012; preserved closest exact-model branch is v42016;
2. no public v42012 binary was found in this pass;
3. rollback/recovery from a bad application image is not yet proven on this exact unit;
4. exact earliest all-key interception seam still needs to be pinned;
5. the support field report confirms intended SD update but its owner failed to trigger the update, so card layout/path/boot condition must be established offline as far as possible first.

Assessment: **clear engineering direction, not yet a responsible one-click installation procedure.**

### Route B — volatile RAM hook through Ditoo MassBoot/service mode

Attractive because it could prove exclusive input **without modifying flash** and could be re-applied at boot.

OpenTivoo shows the family-level concept is real. Ditoo Plus firmware statically confirms a MassBoot path exists, but its exact trigger/protocol remains unresolved.

Assessment: **excellent reversible research route if exact Ditoo MassBoot can be unlocked; not clear enough today.**

### Route C — no-flash code execution through an application parser

Public MiniToo research is exploring this class of route. Ditoo Plus exposes large Bluetooth/media/parser surfaces, so this is conceivable.

Assessment: **research lead only.** It would add exploit-development complexity we do not need if the legitimate Ditoo SD updater is usable.

### Route D — keyboard-board electrical interception / soldering

Could obviously work, but it is contrary to the desired project constraints and appears unnecessary to investigate first.

Assessment: **fallback only.**

## 8. What the next research phase should prove before any flash attempt

### INPUT-R0 — exact key-event map

Disassemble the normal-runtime key path and pin:

- six keyboard-button physical identities -> decoded key IDs/event codes;
- lever path;
- short vs long/repeat representation;
- earliest common dispatch seam;
- whether any stock subsystem consumes a key before that seam.

Success criterion: a table with exact functions/offsets and control-flow evidence, not guesses from string proximity.

### INPUT-R1 — design the minimal consume/forward shim offline

Model a tiny handler:

- if claim inactive: tail-call original dispatcher byte-for-byte;
- if claim active: serialize a bounded input event and return consumed;
- watchdog/TTL/fail-open behavior;
- emergency escape preserved.

Do not write firmware yet.

### UPDATE-R0 — fully document the exact Ditoo SD acceptance state machine

Finish annotating `divoom_check_update`:

- exact path construction;
- card/filesystem prerequisites;
- version comparison rule;
- checksum range;
- partition/file-type selection;
- update completion/reset behavior;
- whether the file is deleted/renamed after success/failure.

### RECOVERY-R0 — obtain a credible rollback story

Before custom flash:

Preferred order:

1. recover exact v42012 bytes from an archive/vendor/source if possible;
2. otherwise establish a read-back path from the purchased unit (ideally volatile MassBoot, no soldering);
3. independently prove a recovery/service path capable of restoring a known-good image;
4. only then treat custom TF update as a live candidate.

A current official v42016 image is useful but is not equivalent to possessing the owner's exact pre-modification v42012.

### PATCH-R0 — offline patcher + verifier

Only after R0/R1:

- patch a copy of exact-model firmware;
- change the minimum bytes possible;
- recompute container checksum;
- self-verify every untouched region/hash;
- disassemble patched control flow;
- simulate claim inactive and active;
- prove stock path remains byte-for-byte reachable when inactive.

### LIVE-0 — first device test should be observational, not exclusive

If live firmware work is eventually authorized, first patch should **report one previously unavailable key while leaving its stock action intact**. This proves delivery + event identity + telemetry before suppression is introduced.

Only after that should a second revision consume the event under an explicit claim.

## 9. Adversarial checks / reasons not to overclaim

- No public project was found that has already installed custom firmware on a Ditoo Plus and taken over its keys.
- The exact reference binary analyzed is v42016; the owner's device is v42012.
- `divoomupdate.bin` is a real SD path in this binary, but the one public support case found failed to make the update trigger.
- The additive container check does not by itself prove every later flash-writing layer lacks a separate condition.
- The large `0xFF` regions in the firmware container are promising space, but this pass did **not** prove those specific regions are resident/executable application code caves. A small in-place shim may make that question irrelevant.
- Multiple higher-level key dispatchers exist. We still need to prove the earliest seam catches every desired key before any stock side effect.
- Power is a separate lifecycle control and should not be lumped into the ordinary seven-control takeover goal.

## 10. Bottom line

The answer changed meaningfully during this pass.

Before this research, full input takeover looked like it might require hardware interception or a deep custom-firmware project with no delivery route.

After exact-binary analysis, the likely architecture is much cleaner:

**Ditoo's keys are already software events, the stock application already centralizes their dispatch, and the exact Ditoo Plus firmware has a real SD-mounted `divoomupdate.bin` updater whose observed integrity gate is the ordinary Divoom marker/version/additive checksum.**

That is enough to justify a focused next phase aimed at a tiny, fail-open **OpenDitoo Input Claim** firmware shim.

I would **not** flash anything yet. The next best work is static: pin the earliest key seam, fully annotate the updater, and solve v42012 backup/recovery. If those three close cleanly, a no-solder full front-panel takeover becomes a very realistic OpenDitoo milestone rather than speculative hacking.

## Public sources used

- Ditoo Plus FCC/manual: https://fccid.io/A8I-DITOO-PLUS
- Ditoo Plus manual PDF/mirror: https://fcc.report/FCC-ID/A8I-DITOO-PLUS/5058746.pdf
- Divoom-support `divoomupdate.bin` field report: https://www.reddit.com/r/Divoom_Products/comments/xt9r45
- REvoom product flags: https://divoom.2a03.party/pflags.html
- REvoom firmware index: https://divoom.2a03.party/fw/versions.html
- Original Ditoo family reference: https://divoom.2a03.party/devices/ditoo.html
- MiniToo custom-firmware research: https://tangled.org/antiali.as/minitoo-forth
- MiniToo delivery analysis/counterexample: https://tangled.org/antiali.as/minitoo-forth/blob/public/docs/flash-delivery.md

## Local evidence used

- `artifacts/firmware/flag42_v42016.bin`
- `PROJECT_STATE.md`
- `notes/OPENDITOO-M7-CONTROL-WORKSHEET-2026-09-09.md`
- `captures/OPENDITOO-M7-KEY-SWEEP-2026-09-09.json`
- `captures/OPENDITOO-M7-AVRCP-KEY-SWEEP-2026-09-09.json`
- `captures/OPENDITOO-BTN2-WINDOWS-RECEIVE-2026-09-10.json`
- `captures/OPENDITOO-BTN7-LEVER-CHARACTERIZATION-2026-09-10.json`

## 11. Fast physical experiment ladder — SD updater without intentional flash

Owner requested a fast experiment using a spare SD card to answer route-selection questions while avoiding a firmware write.

### New cross-branch safety evidence

The preserved flag-60 v60014 Ditoo Plus firmware independently contains the same updater strings at the same offsets as flag-42 v42016 (`DIVOOMUPDATE` at `0x887c`, `divoom_check_update: start update!` at `0x8930`, checksum-error string at `0x8b58`). The broad updater neighborhood around these anchors is ~98.0% byte-identical; the main update routine `0x8394..0x89f9` is ~97.0% byte-identical and its final validation/write region `0x8730..0x89f9` is ~98.0% byte-identical. This is exact-model cross-branch evidence that the validate-before-update architecture is stable across two Ditoo Plus firmware branches, though it still does not prove the owner's v42012 is byte-identical.

### SD-P0 RESULT — PASS (2026-09-12)

Physical owner test passed on a 32 GB microSDHC card reformatted as one ~28.8 GB FAT32 volume. A generated MP3 tone placed at the card root was recognized and played repeatedly by the stock Ditoo Plus. This proves the tested card, FAT32 filesystem, TF slot, stock SD mount path, and normal media read path are all working on the purchased v42012 unit. No firmware-shaped file or `divoom` directory was present during this test.

### Experiment SD-P0 — card compatibility control (negligible firmware risk)

Goal: prove a spare card is compatible with the Ditoo filesystem before putting any update-shaped file on it.

1. Prefer a small known-good microSD/TF card (8–32 GB ideal; manual allows up to 64 GB).
2. Back it up, then use FAT32.
3. Put one harmless MP3 on the card and verify the stock Ditoo can see/play it.
4. No `divoomupdate.bin` is present anywhere.

This exercises only normal documented TF-card media behavior and does not intentionally enter the updater.

### Experiment SD-P1 — filename/path A/B with checksum-poisoned official container (low but nonzero firmware risk)

Goal: determine whether the owner's v42012 actually opens the same SD update path, and whether boot/card-insert behavior gives an observable updater signal, without providing a package that passes the known checksum gate.

Probe payload should start from the preserved official flag-42 v42016 image and change **only the final stored checksum byte**. Example: official tail ends `... 44 49 56 4f 4f 4d 55 50 44 41 54 45 83 21 ab 06`; make the probe end `...83 21 ab 07`. The application body, advertised version `42016`, and `DIVOOMUPDATE` marker stay untouched, but `sum(file[:-4]) mod 2^32 != stored_u32` by construction.

Control/test layout on the same card:

- control: `/divoom/notupdate.bin` = checksum-poisoned official image;
- test: rename the exact same bytes to `/divoom/divoomupdate.bin`.

For each layout:

1. Start from device powered off and product/runtime stopped if practical, so reconnect behavior does not muddy timing.
2. Insert card.
3. Power on normally; do not press any boot combinations.
4. Record time from power press to normal stock UI/Bluetooth availability, any update/error screen, reboot/shutdown, or unusual LED behavior.
5. If the device reaches normal operation, use the official Divoom app to confirm the installed firmware remains v42012; do **not** authorize an app firmware update.
6. Power off normally, remove card, and verify the probe file is still present, same size and same hash. Deletion/mutation would be strong evidence the updater touched it; unchanged is inconclusive.
7. If the exact-path boot test is silent, one optional follow-up is inserting that same poisoned card while already powered on to see whether SD insertion triggers the checker. Do not proceed to a valid package.

Interpretation:

- exact-name test causes a repeatable delay/UI/reboot difference vs `notupdate.bin`, while firmware remains v42012 -> strong evidence that v42012 recognizes the path/container and reaches validation;
- probe file is deleted/changed while firmware remains v42012 -> strong positive updater-touch evidence;
- no difference -> inconclusive, not a disproval; v42012 may trigger under another lifecycle condition or reject before anything visible;
- firmware version changes or an actual update screen/progress begins -> unexpected; do not interrupt power mid-update. Preserve observations and stop the experiment after the device reaches a stable terminal state.

### Risk boundary

`SD-P0` is ordinary stock use and is effectively no firmware-risk beyond normal SD-card use.

`SD-P1` is **low but not zero risk**. Exact v42016 and exact-model flag60 v60014 both show the update body is validated and checksum failure is rejected before the accepted `start update` path; their updater regions are ~97–98% identical. However, the owner's installed v42012 binary has not been recovered, so its exact ordering is not proven. A parser bug, materially different older updater, or unexpected recovery behavior remains possible. Keep stable battery/USB power available and never intentionally interrupt the device if it unexpectedly shows real update progress.

A **valid official v42016 package** is not part of this experiment: it would intentionally modify flash and should be considered moderate/high preservation risk until v42012 backup/recovery is solved. A **checksum-valid patched package** remains high risk and is explicitly out of scope.

### What this experiment answers

A positive SD-P1 result materially promotes Route A (fail-open key hook delivered through TF/SD) because it proves the exact owner's v42012 participates in the same physical delivery path. A negative result does not kill Route A but shifts priority toward finishing trigger-state analysis or Route B (volatile MassBoot/readback/recovery) before any flash attempt.

### SD-P1 HISTORICAL PREP — superseded by the consumed result below (2026-09-12)

A one-use physical experiment manifest is frozen at `experiments/OPENDITOO-SD-P1-001.json` (manifest SHA-256 `96d7537e558ddfea3b00196217f4d15520f2bcd351b602db1eeecd768d097954`). The local probe is `.openditoo-local/sd-p1/openditoo-sd-p1-v42016-checksum-poison.bin`, size 1,207,313 bytes, SHA-256 `acf0715fc98ecc1dd1abce483a0c68d8ca7b3bf98f676b03bdedacc72bc0ba43`. It differs from preserved official flag42 v42016 at exactly one byte: final file byte `0x06 -> 0x07`. The official calculated/stored additive checksum is `0x06ab2183`; the probe stores `0x07ab2183` while its calculated checksum remains `0x06ab2183`, so it fails the known acceptance gate by construction.

At this historical preparation point no SD-P1 device test had yet been authorized or executed. It was later granted once, executed, and consumed; the authoritative result is recorded below and in `experiments/OPENDITOO-SD-P1-001.json`.

### SD-P1 PHASE B RESULT — STRONG POSITIVE (2026-09-12)

The one-use checksum-rejection probe produced filename-specific physical behavior on the purchased v42012 unit. The control path `/divoom/notupdate.bin` booted normally with no updater UI. With the exact same frozen bytes renamed to `/divoom/divoomupdate.bin`, owner video shows a clear download/update arrow entering a tray around 10 seconds after power-on; this icon was absent from the control. The device then continued through stock startup visuals/Bluetooth and OpenDitoo returned.

Interpretation: **strong evidence that the purchased v42012 unit recognizes and enters the SD updater path using the exact filename/path**. Because the payload's known additive checksum is intentionally invalid, this demonstrates updater-path recognition without intentionally supplying an acceptable package. Optional powered-insertion Phase C is unnecessary and will not be run.

Pending closure checks: verify the probe file remains byte-identical on the card (SHA-256 `acf0715fc98ecc1dd1abce483a0c68d8ca7b3bf98f676b03bdedacc72bc0ba43`) and confirm installed firmware remains v42012. No checksum-valid update should be attempted until recovery/readback is solved.

### SD-P1 RESULT — PASS / positive updater-path recognition (2026-09-12)

The one-use `OPENDITOO-SD-P1-001` experiment is complete and consumed. On the same 32 GB FAT32 card proven by SD-P0, the checksum-poisoned official v42016 bytes produced a normal control boot when named `/divoom/notupdate.bin`. Renaming the exact same bytes to `/divoom/divoomupdate.bin` produced a distinct stock updater/download-to-tray UI that was absent from the control boot; the device then continued through normal stock startup and OpenDitoo returned. Afterward the file remained present and byte-identical at SHA-256 `acf0715fc98ecc1dd1abce483a0c68d8ca7b3bf98f676b03bdedacc72bc0ba43`. Optional powered-insertion Phase C was not run because the cold-boot exact-path result was already positive.

**Conclusion:** the SD firmware-delivery path is now physically proven on the purchased v42012 Ditoo Plus. The probe did not pass the known additive checksum gate and did not mutate on card. This materially promotes Route A. It does **not** authorize or prove safe installation of a checksum-valid image; recovery/readback remains the blocker before intentional flash.

A later independent stock factory/test-mode observation (`OPENDITOO-FACTORY-TEST-OBS-001`) displayed `42 / 012`, closing the firmware-version postcheck: the unit still reported flag 42 / v42012 after SD-P1.


## 12. INPUT-R0 / RECOVERY-R0 acceleration — exact key table and MassBoot gate (2026-09-12)

This section records static work performed after the physical SD-P1 positive. No new device I/O occurred.

### Exact board-config key table

The flag-42 v42016 Ditoo Plus image carries the analog-key configuration beginning at file `0x60d0`. Seven calibrated analog records map physical-key ladder ranges to key IDs 1..7. Immediately afterward, the translation table at file `0x6119` contains eight 4-byte records of the form `[key_id, short_event, long_event, third/repeat]`:

| key ID | short event | long event | third/repeat | physical mapping |
| ---: | ---: | ---: | ---: | --- |
| 0 | `0x47` | `0x47` | `0x47` | separate power/system key path |
| 1 | `0x43` | `0xFF` | `0xFF` | **M** |
| 2 | `0x16` | `0x16` | `0xFF` | **+** |
| 3 | `0x67` | `0x67` | `0xFF` | **Lighting** |
| 4 | `0x5F` | `0xFF` | `0xFF` | **Left** |
| 5 | `0x0C` | `0x0C` | `0xFF` | **-** |
| 6 | `0x60` | `0x60` | `0xFF` | **Right** |
| 7 | `0x15` | `0x6B` | `0xFF` | **Lever** |

Physical mapping confidence is high: the exact manual numbers the six keyboard controls plus lever in this same order, exact-unit runtime evidence independently fixes IDs 4/6 as Left/Right, and the boot configuration below independently identifies ID1 as the M factory/test key and ID3 as the MassBoot key. The product-test key state machine at `0x16f06` expects the six-event sequence `0x16,0x67,0x5f,0x0c,0x60,0x15`, matching IDs 2..7.

This materially closes the *identity* half of INPUT-R0. The remaining INPUT-R0 work is to select the earliest practical hook seam that sees the decoded event before feature-specific stock consumers, not to rediscover which physical button is which.

### Exact Ditoo Plus MassBoot/test-mode selector

The same `key` config contains two 3-byte boot-selector triplets:

- file `0x6113..0x6115`: `[1,3,5]` — enabled, **key ID3**, five stable samples -> MassBoot selector;
- file `0x6116..0x6118`: `[1,1,5]` — enabled, **key ID1**, five stable samples -> factory/test selector.

Function `0x1b8f4(mode)` loads the `key` config and verifies the selected key over a bounded five-sample window with ~100 ms delays. On `mode != 0` success it logs `enter massboot!` (string at `0x1ba48`) and transfers to the low-level MassBoot routine through `0xA6460`; on `mode == 0` it logs `enter test mode!` (`0x1ba58`).

The startup caller around `0x1bb18` first checks `0x1b8f4(0)` for test mode. On the normal path it then configures GPIO `0x1E` (decimal 30), waits ~100 ms, reads it through the low-level GPIO-read veneer (`0xA6430`), and calls `0x1b8f4(1)` only when GPIO30 reads high. Thus the exact reference firmware's MassBoot condition is:

`GPIO30 high + key ID3 (Lighting) stably held at startup`.

GPIO30 is very likely the external-power/charging condition rather than another front-panel input: nearby Ditoo startup/offline-charge code repeatedly reads GPIO30, while the AK1052D datasheet multiplexes GPIO[30] with `ISENSE` (charger-current sense). The same datasheet advertises USB Mass Storage Boot as a hardware bootstrap mode. This supports a narrowly testable physical hypothesis: **data-capable USB/external power attached + Lighting held during ordinary startup enters MassBoot**. Treat this as high-confidence static inference until the purchased v42012 unit enumerates differently in a bounded live test.

### Recovery consequence

Because SD-P1 physically proved the updater path but a checksum-valid flash remains unjustified without rollback, the next live milestone should be **enumeration-only MassBoot discovery**, not a valid firmware update. If the exact unit exposes a service/boot USB identity, that becomes the preferred route to investigate readback/volatile execution before any persistent patch. No MassBoot command semantics, VID/PID, memory addresses, or Tivoo USB behavior are transferred by assumption.


### MASSBOOT-ENUM-001 RESULT — boot-path positive / host-enumeration negative (2026-09-12)

The one-use `OPENDITOO-MASSBOOT-ENUM-001` experiment is complete and consumed. Windows ordinary PnP enumeration contained 44 present devices in the normal USB-attached baseline, 44 while the Ditoo was disconnected between phases, and 44 in the Lighting+USB candidate; both candidate deltas were exactly zero. No Ditoo-specific VID/PID, disk, WPD, HID or other PnP identity appeared, and the runner sent no custom USB/SCSI/vendor command and performed no firmware/RAM read or write. Evidence is under `captures/private/massboot-enum-001/20260912T053813Z/`.

The operator independently observed that the Ditoo **did not complete normal boot while Lighting was held** during the candidate. This is strong behavioral support for the exact static selector (`GPIO30 high + key ID3 / Lighting -> 0x1b8f4(1) -> MassBoot transfer`) but is not equivalent to USB enumeration proof. Importantly, the normal baseline also exposed no Ditoo USB/PnP identity, so the null candidate delta does not distinguish "MassBoot was not entered" from "the retail USB-C path does not expose the SoC service USB data interface / requires a different physical topology." Do not automatically repeat this experiment.

Public FCC internal photos show the USB-C receptacle mounted directly on the main Anyka board, but are insufficient to prove D+/D- routing to the SoC; the public FCC listing withholds the schematic itself. Therefore Route B remains technically real but **not presently accessible through a proven no-solder retail-USB transport**. Route A (the physically proven SD updater) remains the preferred delivery route once rollback/readback is solved.


### MASSBOOT-ENUM-002 RESULT — HOST ENUMERATION NEGATIVE (2026-09-12)

A fresh one-use repetition with a replacement USB cable produced the same Windows-side result as ENUM-001: 44 relevant PnP entries at normal-USB baseline, 44 while disconnected, and 44 in the Lighting-held MassBoot candidate state, with zero new identities versus either baseline. No custom USB/SCSI/vendor command, firmware/RAM read, or device write was issued. If the replacement cable was independently verified data-capable as required by the experiment manifest, this materially weakens the charge-only-cable hypothesis. Combined with the earlier physical boot-path change under Lighting, the working interpretation is: the MassBoot selector is behaviorally supported, but the retail USB-C path does not expose a host-visible service transport under the tested condition. Further cable-swap enumeration repeats are not a priority; the physically proven SD updater remains the preferred no-solder delivery path.

### Factory/test-mode observation — OPENDITOO-FACTORY-TEST-OBS-001

Passive exact-unit observation on 2026-09-12 confirms the M-at-boot branch reaches the stock Ditoo Plus factory/product-test environment. With the SD card removed and no controls pressed after entry, the display settled on `42` over `012`. This is strong direct on-device evidence for product/update flag 42 and installed firmware v42012. No later factory-test stage was advanced and no persistent write was observed.


## 13. FIRM-R0 disassembly — the true common key-event fan-in (2026-09-12, offline)

Static disassembly (capstone Thumb, flat image, load base 0 — confirmed because every BL in
the keypad module resolves exactly to a known file offset). No device I/O. This pins the
earliest guaranteed-common seam INPUT-R0 left open, and corrects the working assumption that
the emitter `0x52656` is that seam.

### Runtime event graph (flag42 v42016 offsets)

```
poll tick
  -> key_state_machine 0x52790       debounce/hold timing; short <1000ms vs long >=1000ms
       -> get_current_key 0x526f2 -> [RAM driver ptr] adc_decoder 0x52844
            -> adc_read_veneer 0xc6764   6 samples, drop min+max, average -> counts
            -> compare vs 7 calibrated ranges -> key id
       -> translated_event_emitter 0x52656   (short/long PRESS)
            -> translation_mapper 0x52926    pick short/long/repeat from 4-byte record
            -> queue_post 0xc6d7c            category 0x82
       -> 500ms auto-repeat timer -> repeat_handler 0x52982
            -> queue_post 0xc6d7c            category 0x82   [BYPASSES the emitter]
  -> stock consumer task dequeues category 0x82
```

`adc_decoder 0x52844` has zero BL callers and no flash literal pointer: it is registered as a
RAM driver callback and invoked via `blx` from `get_current_key 0x526f2` (`[base+0xc]+4`).
`key_state_machine 0x52790` is likewise a registered poll callback (no BL caller, no literal).

### The seam is the category-0x82 queue post, not the emitter

The emitter `0x52656` only handles short/long PRESS. Auto-repeat and key-change finalize post
to the queue directly. The single fan-in catching short + long + repeat is the category-`0x82`
post `queue_post 0xc6d7c` (`os_post(category r0, event r1, u16 param r2)`, a generic
ring-buffer enqueue). Exactly four category-`0x82` producers:

| site (flag42) | source | event byte | class param |
| --- | --- | --- | --- |
| `0x52680` | emitter, translated short/long press | translated / raw key id | phase<<8 \| 2 |
| `0x52916` | release-finalize: current key short event | record byte1 | 2 |
| `0x529aa` | repeat handler: previous key short on key change | record byte1 | 2 |
| `0x529ce` | repeat handler: auto-repeat fire | record byte3 | 3 |

An adjacent producer `0x525a8` posts a different class **`0x81`** and is not a translated key
event (do not hook it for key takeover).

### Translator (`0x52926`) contract

Return code steers the emitter: `0` emit translated byte written to `*out`; `1` emit the raw
key id (no table present); `2` key id not found → drop; `3` repeat/third handler `0x52982`
invoked → emitter emits nothing (handler posts on its own). Record layout confirmed
`[key_id, short(byte1), long(byte2), third/repeat(byte3)]`; `0xFF` in a phase column means
"no distinct event, fall back to short byte1".

### Byte-verified constants

Long-press threshold **1000 ms** (`movs r1,#0x7d; lsls r1,#3` = `0x3e8`), auto-repeat period
**500 ms** (`movs r0,#0xff; adds r0,#0xf5` = `0x1f4`), scan reschedule **10 ms** (`#0x0a`).

### Cross-branch conservation

flag60 v60014 is the same subsystem shifted by exactly **`-0x94`**, including the far
`queue_post` (flag60 `0xc6ce8`). Category `0x82` and the emitter/translator/decoder bodies are
conserved (48/48, 92/92, 134/134 identical per the locator). This makes a signature-located
shim branch-portable rather than hardcoded to one build.

### Hook-seam consequence for PATCH-R0

A fail-open consume-or-forward shim must hook the category-`0x82` path — either wrap the four
producers or (single point) intercept the consumer dequeue of category `0x82` — **not** the
emitter alone, or auto-repeat and finalize events would leak past the claim. Signature-locate;
never hardcode one build offset.

### Delivered offline (no flashable output)

- `tools/keypad_pipeline_report.py` — fail-closed byte-verifying analyzer (pure Python; the
  Thumb-BL decoder is ARMv5T T1, validated against known targets in tests).
- `artifacts/analysis/keypad_pipeline.json` — committed machine-readable model, PASS on both
  branches, pins live firmware sha256s.
- `tests/test_day1_offline.py::FirmwareKeypadPipelineTests` — 5 tests (locator PASS both
  branches; locator FAIL-CLOSED on a mutated emitter byte; BL decoder vs known targets;
  category-`0x82` fan-in verified both branches; committed artifact vs live bytes). Verifier
  total now 331 tests PASS.

## 14. UPDATE-R0 disassembly — container format + acceptance gates (2026-09-12, offline)

`divoom_check_update` disassembled at flag42 file `0x8394` (link base **`0x08400000`**: code
BL read as base 0 because PC-relative; absolute rodata string pointers confirm the real base
`0x08400000`, so the earlier note that the "update routine" sits at `0x8394..0x89f9` was
conflating the code with its adjacent rodata string block `0x886c..0x8967`).

### Container format (verified on both preserved branches, last 20 bytes)

```
[ version : u32 LE ][ "DIVOOMUPDATE" : 12 bytes ][ checksum : u32 LE ]
  file[-20:-16]        file[-16:-4]                 file[-4:]
```

- flag42 v42016: version `42016`, checksum `0x06ab2183` == `sum(file[:-4]) & 0xffffffff`.
- flag60 v60014: version `60014`, checksum `0x06ab2798` == `sum(file[:-4]) & 0xffffffff`.
- The additive checksum covers the version field and marker; only the final stored u32 is
  excluded. No cryptographic signature/HMAC is present in this path.

### Acceptance gates (firmware evaluation order; reject at first failure)

1. **marker** `0x8744`: `memcmp(header+5, "DIVOOMUPDATE", 12)` via `0xa2850`. Mismatch clears a
   header byte and rejects.
2. **version** `0x878c-0x879a`: `bl 0x34308` (installed version) `cmp` candidate; `bhs` →
   reject when `installed >= candidate` (no downgrade, no same-version reinstall). A header
   flag byte `== 0x33` ('3') at `0x8790` bypasses this gate (forced update).
3. **checksum** `0x87be`: `subs r2,#4` sets coverage to `file[:-4]`; chunked 1024-byte reads
   accumulate an additive byte sum (`0x87ee`); `0x8820` compares to the stored u32. Mismatch
   rejects before any write.
4. **write** `0x883c`: only after all gates pass, `bl 0x3a824(mode=0, data_len, checksum,
   version)` — the flash writer — then reset. Erase granularity / partition map / reset path
   inside `0x3a824` are not yet disassembled (future UPDATE-R0 work).

This matches the log-string order (`flag err` → `pass version` → `read over` → `start update`)
and explains SD-P1 precisely: the checksum-poisoned probe passed the marker and reached the
updater UI but failed the checksum gate, so nothing was flashed and the file stayed
byte-identical.

### Delivered offline (read-only; no installable package)

- `tools/ditoo_update_container.py` — parser/validator (`--selfcheck`) reporting each gate in
  firmware order; accepts v42016 as an upgrade from 42012, rejects it as a reinstall on 42016.
- `tests/test_day1_offline.py::UpdateContainerTests` — 6 tests incl. negative fixtures derived
  from the real firmware (checksum poison → checksum gate; bad marker → marker gate first;
  force-flag bypass; truncated → parse failure).

## 15. PATCH-R0 prototype — offline, non-deployable fail-open hook model (2026-09-12)

`tools/openditoo_patch_prototype.py` composes FIRM-R0 (the category-0x82 seam) and UPDATE-R0
(the container validator) into a research transformer with hard safety properties:

- **fail closed** on unrecognized firmware (refuses `tivoo_31102.bin`);
- **signature-locates** the seam and derives the branch shift (0 / 0x94); no hardcoded build;
- **verifies original bytes** at all 4 category-0x82 producer sites (`movs r0,#0x82` + `bl
  queue_post`) before modelling any edit;
- **models the fail-open redirect** by re-targeting each producer BL to a caller-supplied
  `shim_entry` using a correct Thumb-BL encoder (round-trips the decoder, validated against the
  real emitter BL bytes);
- **non-installable by construction** — an emitted research image has an invalid stored updater
  checksum, and the tool re-runs the UPDATE-R0 validator to PROVE the updater rejects it at the
  checksum gate, refusing to emit anything that would pass;
- **reports changed regions** + an untouched-region SHA-256 tamper witness.

Deliberately NOT done (LIVE-gated): authoring the shim machine code (claim/heartbeat +
forward-or-consume), proving any all-0xFF region is a resident/executable cave, recomputing a
valid checksum, or writing a device. The prototype stops at the verified seam-redirect model.

Tests: `PatchPrototypeTests` (5). Verifier total: 342 PASS.

## 16. FACTORY-R0 disassembly — product-test state machine (2026-09-12, offline)

Disassembled the stock product-test dispatcher/router and the key-test stage (flag42, link
base 0x08400000). No device I/O.

- **Entry:** M-at-boot -> `0x1b8f4(0)` -> `enter test mode!` -> `divoom_product_test`.
- **Event router `0x16d3e`:** active only in product-test mode (`global[0]==2`). The **M short
  event `0x43`** is the stage advance/route key; stage handlers are dispatched by id
  (4,5,6,7,8,9,0xc,0xd,0xe,0xf) through `0x2e522`.
- **Advance `0x16d08`:** increments a volatile RAM step index (`[state+4]+0xa`); at a stage's
  last step, moves to the next stage id. **Never auto-advances** — hence the passive
  observation held on stage 0 (`42 / 012`).
- **Stage 0:** passive product-flag/version display (`42 / 012`). Read-only.
- **Key-test stage (id 7, `0x16ef6`): READ-ONLY.** Verifies +,Lighting,Left,-,Right,Lever
  (`0x16,0x67,0x5f,0x0c,0x60,0x15`) pressed in order; increments a volatile counter; on
  completion calls advance and logs `key test is over!`. No flash/SPI write. Safe to observe.
- **SPI-flash-check stage (`divoom_product_test_spiflash_check`, name `0x16d88`):** body not
  fully disassembled; image has `Fwl_spiflash_write`/`Fwl_spiflash_erases`. **Classified
  conservatively as potentially persistent-write — do NOT enter until its target is proven a
  scratch region.**
- **charge/sd/disp stages:** read/measure + display-only; lower priority; treat read-only
  pending confirmation.

**Safe route (if a live factory visit is ever justified):** stage 0 (passive) -> advance with M
to key-test (id 7) -> exercise the six keys; stop before the SPI-flash stage. No factory
observation is authorized at this handoff.

## 17. TELEMETRY-R0 — least-invasive report channel (2026-09-12, offline)

**Decision: reuse the already-initialized stock SYS SPP device→host response path.** The
firmware brings up a framed, checksummed SPP command/response service at boot (`SYS SPP init!`
`0xf72c`, `[SYS:SPP]check sum err` `0xf7c4`, `SYS_SPP_OKCommandACK` `0x22fe8`, typed commands
incl. `SPP_GET_DEVICE_INFO` `0x12357`). This is the **same RFCOMM/SPP stack OpenDitoo already
uses for image transport**, so the Host already parses it — no new Bluetooth service, socket, or
frame builder. The device→host direction is independently proven on the exact unit by the
unsolicited `0x09`/`0xBD` RFCOMM reports that already reach Windows (BTN-2/BTN-7).

The first observe-only firmware revision should emit one small typed SPP key-report per claimed
key (a spare/new typed report the Host can distinguish, reusing the existing frame builder +
checksum) while still posting the stock category-0x82 event — strictly additive and fail-open.
Rejected as primary: piggybacking `0x09`/`0xBD` unsolicited reports (tied to specific stock
behaviors + reclaim side effects) and AVRCP pass-through (that is the stock action for
Left/Right/lever and absent for M/+/Lighting/-). No generic raw-memory API; the public surface
stays typed/capability-scoped.
