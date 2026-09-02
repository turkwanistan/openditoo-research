# OpenDitoo Research

Preservation-first reverse-engineering workspace for the Divoom Ditoo Plus.

## Project state

Start with [`START_HERE.md`](START_HERE.md), then read [`PROJECT_STATE.md`](PROJECT_STATE.md) for the comprehensive current research synthesis, evidence calibration, physical-session plan, and ranked next work.

## Artifact preservation

Public artifacts acquired during reconnaissance are stored under `artifacts/` and intentionally committed to local Git so future work does not depend on Divoom CDN or FCC mirror availability.

Key preserved artifacts as of 2026-09-02:

- Ditoo Plus product-flag 60 firmware v60014
- Ditoo Plus product-flag 42 firmware v42016
- original Ditoo product-flag 46 firmware v46032 (family calibration)
- Tivoo OTA v31102 (family comparison reference)
- ten public FCC A8I-DITOO-PLUS exhibits, including internal photos, manual, test report, and labels
- exact OTA query responses/provenance and historical 60010/42010 metadata
- `artifacts/SHA256SUMS` and `artifacts/SHA1SUMS`

The downloaded FCC files' SHA-256 values match FCCID.io's published hashes. The Divoom firmware SHA-1 values match the live OTA API responses, and SHA-256 values were independently recorded locally.

## Not yet recovered

These are metadata/leads only and are **not** present as binary artifacts:

- Ditoo Plus firmware v60010 (`L1ghbmA929aEUhOCAAAAAD9iqis747.bin`) — historical CDN URL now 404
- Ditoo Plus firmware v42010 (`eEwpPWA93ECEIZjCAAAAAArkYGQ617.bin`) — historical CDN URL now 404
- support-issued historical `divoomupdate.bin`
- period-correct Divoom 3.1.x Android APK (available hosts encountered human/Cloudflare gating)
- permanently confidential FCC schematics/block diagram/operational description

Do not infer that family-reference artifacts are exact purchased-unit evidence. Preserve the MATCHED / RELATED / LEAD calibration used by the research dossier.
