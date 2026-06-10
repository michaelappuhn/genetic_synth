# Specs

Per-milestone design specs for the Rytm genetic-algorithm sound-design tool. See `../../CLAUDE.md` for project-wide context.

| # | Milestone | Goal | Status |
|---|-----------|------|--------|
| M0 | [Foundation cleanup](M0-foundation-cleanup.md) | Tidy module imports, drop legacy code, add `deap` | Shipped |
| M1 | [End-to-end GA loop](M1-end-to-end-ga-loop.md) | Run one DEAP-driven run on one channel with LPD8 voting | Shipped |
| M2 | [Quality of life](M2-quality-of-life.md) | Logging, replay-best, CLI config, elitism, clean shutdown | Shipped |
| M3 | [Persistence](M3-persistence.md) | Save / resume runs, optional SysEx dump to Rytm | Next |
| M4 | [Better fitness & diversity](M4-fitness-and-diversity.md) | Mini-tournaments, adaptive mutation, niching | Not started |
| M5 | [Device abstraction](M5-device-abstraction.md) | Refactor for multi-device: `Device`, NRPN/CC parameters, audition strategies | Not started |
| M6 | [Mopho port](M6-mopho-port.md) | Add DSI Mopho as second device, exercising the CC + NRPN paths | Not started |
| M7 | [Multi-device evolution](M7-multi-device-evolution.md) | Evolve a genome spanning two devices (e.g. Rytm + Mopho), layered or sequential audition | Not started |

## Conventions

- Each spec is independently executable — finish M(n) before starting M(n+1)
- "Files" sections name the modules touched; specific function signatures are decided during implementation
- "Verification" sections describe how to confirm the milestone works end-to-end (the Rytm is required from M1 onward)
- Hardware required: Elektron Analog Rytm MKII (MIDI port name: `Elektron Analog Rytm MKII`), Akai LPD8 on Prog1 (port name: `LPD8`). DSI Mopho is required from M6 onward (port name varies — likely `Mopho` or via a USB MIDI interface).

## Locked design decisions (from brainstorming, 2026-06-09)

- **Unit of evolution:** one channel, evolving machine choice + per-voice CCs (Synth general / Filter / Amp / LFO)
- **Audition:** single trigger, single 1–8 LPD8 vote per individual
- **GA library:** [DEAP](https://github.com/DEAP/deap)
- **Genome shape:** typed sequence `[machine_idx, cc_val_0, ..., cc_val_N]` with per-gene bounds drawn from `rytm-limited.csv` and `AnalogRytmMachineSelector`
