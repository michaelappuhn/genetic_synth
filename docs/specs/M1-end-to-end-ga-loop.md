# M1 — End-to-end GA loop

## Context

This is the "hello world" milestone — the first moment the genetic algorithm actually breathes. The point isn't a sophisticated GA; it's to prove that the wires connect: DEAP can produce candidates, candidates make it to the Rytm as CCs + a note trigger, the LPD8 vote comes back as fitness, and a second generation sounds different from the first because of that vote. Everything in M2–M4 is unlockable from here.

## Scope

**In:**
- One new module wiring DEAP to the existing `synthesizer/` and `user_interface/` code
- Hardcoded run config (channel, pop size, generations, mutation rate, tournament size) — no CLI yet
- A driver script that runs one GA session start-to-finish

**Out:**
- Logging beyond `print`, persistence, replay, CLI flags (all M2)
- Saving champion patches to disk or device (M3)
- Adaptive mutation, mini-tournaments, niching (M4)

## Approach

### Genome shape

A DEAP `Individual` is a list of ints:

```
[machine_idx, cc_val_0, cc_val_1, ..., cc_val_{N-1}]
```

- `machine_idx` is an index into `AnalogRytmMachineSelector.avail_machines_by_channel[channel]` (not the raw machine number — keeps mutation/crossover bounded by the per-channel list length)
- `cc_val_i` is the integer CC value for the i-th parameter in the curated `ParameterCollection` returned by `AnalogRytmParameterCSVReader`. Bounds are per-gene, drawn from `param.value_min` / `param.value_max`
- `N` is fixed for a run because the parameter list is fixed at startup

### DEAP toolbox

- `creator.create("FitnessMax", base.Fitness, weights=(1.0,))`
- `creator.create("Individual", list, fitness=creator.FitnessMax)`
- `toolbox.register("individual", ...)` — generate one random individual respecting per-gene bounds
- `toolbox.register("population", tools.initRepeat, list, toolbox.individual)`
- `toolbox.register("mate", tools.cxTwoPoint)` — vanilla two-point crossover
- `toolbox.register("mutate", bounded_mutate, indpb=0.15)` — custom; see below
- `toolbox.register("select", tools.selTournament, tournsize=2)`
- `toolbox.register("evaluate", evaluate)` — see below

### Custom mutator

`tools.mutUniformInt` doesn't support per-gene bounds. Write a small mutator that, for each gene with probability `indpb`, samples a new value uniformly in that gene's `[lo, hi]`:

```
bounds = [(0, len(machines) - 1)] + [(p.value_min, p.value_max) for p in params]
```

Build `bounds` once at startup and close over it. Keep this in the new `genetic/` module — it doesn't belong in `synthesizer/`.

### Evaluation (the fitness function)

`evaluate(individual)`:
1. Translate `machine_idx` to a machine number; translate the CC tail to a `ParameterCollection` by setting each `Parameter.value` from the genome (don't mutate the canonical collection — clone or rebuild)
2. Send the machine selection over MIDI
3. Send the CC collection via `AnalogRytmMidiMessageCollectionSender.send_collection_messages()` (or a thin wrapper that doesn't re-randomize)
4. Trigger one `note_on` on the channel, brief sleep, `note_off`
5. Call `LPD8VoteController.get_vote()` — blocks until a pad press
6. Return `(vote,)`

### Driver

A new top-level script (`run.py` or `genetic/main.py`) that:
- Opens `MidiConnection('Elektron Analog Rytm MKII')`, asserts connected
- Opens `LPD8VoteController`, asserts connected (fall back to keyboard if not)
- Builds the toolbox for a fixed channel
- Calls `algorithms.eaSimple(pop, toolbox, cxpb=0.5, mutpb=0.3, ngen=5, verbose=True)`
- Prints final best individual + its decoded machine name

### A note on the existing Rytm sender

`AnalogRytmMidiMessageCollectionSender.__init__` currently *generates* a random parameter collection and *selects* a random machine internally (`synthesizer/midicontrol.py:108–124`). For M1, the GA owns those decisions — the sender should accept a pre-built `ParameterCollection` and a pre-chosen machine instead. Two options:

1. Add a constructor parameter for a pre-built collection and skip the internal randomization when provided
2. Bypass the high-level sender and use `MidiMessageCollectionSender` (its parent class) directly, plus a separate machine-CC send

**Recommended: option 2** for M1. Keeps the existing sender alone (still useful as a "give me a random patch" tool) and avoids a constructor-flag mess. The GA driver constructs a `MidiMessageCollectionSender` with the genome-derived collection and sends the machine CC itself.

## Files

New:
- `genetic/__init__.py`
- `genetic/genome.py` — bounds computation, individual factory, custom mutator
- `genetic/evaluate.py` — the fitness function (closes over MIDI connection + voter)
- `genetic/main.py` — driver entry point

Touched:
- `synthesizer/midicontrol.py` — *no changes required if option 2 above is taken*. If option 1 is taken later, add an optional `parameter_collection` parameter to `AnalogRytmMidiMessageCollectionSender.__init__`

## Verification

End-to-end, with hardware:

```bash
# Both devices connected
python -m genetic.main
# - Prints connection status for Rytm and LPD8
# - Plays 4 candidates from generation 0, each followed by a vote prompt
# - Prints generation summary (best/avg fitness)
# - Repeats for 5 generations
# - Prints final champion: machine name + CC values
```

Success criteria:
- Each candidate produces an audibly distinct sound on the Rytm
- Voting 8s repeatedly on candidates with a particular sonic character causes later generations to drift toward that character
- Voting 1s on everything causes the algorithm to keep searching (high diversity persists)
- The run completes without exceptions and the printed champion can be re-sent manually to confirm it matches what was heard

## Open questions deferred to implementation

- How long to hold the trigger note? Probably 100ms; revisit if percussive voices feel cut off
- Should mutation of the machine gene be rarer than CC genes? (Switching machine is a bigger semantic jump.) Plausible but premature — leave at uniform `indpb` for M1
