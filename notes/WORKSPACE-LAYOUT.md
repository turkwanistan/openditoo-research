# OpenDitoo workspace

WSL checkout: `/home/wan/Projects/openditoo-research`
WSL_MCP project: `openditoo-research` (automatically discovered under the configured Projects root).

Verified on 2026-09-08: project discovery, repository reads, offline command execution and project-scoped writes. Clone basis: `1e4fd0704a4e6d95f9b139ea383307765aa38dcb`. Both preserved Ditoo firmware SHA-256 values match their provenance and the inspected OptiPlex copies.

| Path | Purpose |
| --- | --- |
| START_HERE.md | Hydration entry point |
| PROJECT_STATE.md | Canonical project synthesis |
| artifacts/ | Preserved firmware, FCC documents, reference material and provenance |
| captures/ | Exact-unit observations and Bluetooth captures; exclude unrelated personal data |
| experiments/ | Bounded experiment manifests and corresponding results |
| notes/ | Plans, analysis and handoffs |
| host/ | Offline protocol and frame logic |
| cli/ | Typed WSL command interface |
| runtime/windows/ | Separate Ditoo Windows Host and setup scripts |
| tests/ | Offline protocol and behavior checks |

Empty implementation directories are placeholders only; no CLI, Windows Host, dependencies, scheduled task or device connection has been installed. Git placeholder files preserve the intended layout when committed.

Next environment step: inspect the live OpenTivoo build and authenticated Windows-localhost access, then implement only the minimum separate Ditoo tooling needed by the Day-1 plan. Preserve the active Tivoo installation. Ditoo must not inherit its target identity, endpoint, credentials, state directory or transmission authority.

The current task prioritizes application-level portability over the older MassBoot research priorities in START_HERE.md. No device actions are performed by this workspace setup.
