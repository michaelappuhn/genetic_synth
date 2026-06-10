# M4 — Better fitness signal & diversity

## Context

By M3 the GA works end-to-end and patches are durable. The remaining problem is qualitative: with a coarse 1–8 absolute vote and vanilla tournament selection, runs tend to converge fast on whatever the user voted highly in the first generation — and the user's sense of "what an 8 means" drifts over a long session. DeLanda's framing wants surprise and generative range; this milestone is about defending that against the user's own consistency drift and the algorithm's tendency to mode-collapse on a single sound family.

## Scope

**In:**
- Optional **mini-tournament voting mode**: instead of rating one candidate 1–8, audition two back-to-back and pick the winner. More reliable signal, slower per generation.
- **Adaptive mutation**: bump mutation rate when the population's best fitness plateaus; lower it when the population is exploring well.
- **Niching / shared fitness**: penalize candidates that are too genetically similar to other high-fitness candidates, preserving timbral diversity.

**Out:**
- Anything that requires audio analysis (FFT-based fitness, automatic similarity from audio). We're staying on the LPD8/keyboard input for fitness; "similarity" here means genome distance, not audio distance.
- Multi-channel / kit-wide evolution. Belongs in a later milestone if at all.

## Approach

### Mini-tournament voting

A run flag `--vote-mode {absolute, tournament}` (default `absolute`). In tournament mode:
- Each generation, pair candidates randomly into 2-individual heats
- For each heat: play A, brief gap, play B, brief gap, repeat once
- Voter presses pad 1 for A or pad 2 for B
- Winner gets fitness `1.0`, loser `0.0` for that heat; multiple heats per generation give a fractional fitness
- Selection then works on these continuous fitnesses

This requires `LPD8VoteController` to gain a `get_choice(n_options=2)` method that maps pads 1..N to choices and ignores the rest. Keep the existing 1–8 `get_vote()`.

The mini-tournament is a hedge against rating drift (you don't have to remember what a "7" meant 40 minutes ago — you only have to remember which of two sounds you heard 5 seconds ago). The cost is doubled audition time per pairwise comparison; with `pop_size=4` and 3 heats per generation that's 6 trigs per generation instead of 4.

### Adaptive mutation

Track `best_fitness` per generation in a sliding window (window = 5 generations). If the slope of that window is flat (best hasn't improved by > 0.5 in 5 generations), multiply mutation rate by 1.5. If best is improving (> 1.0 over the window), multiply by 0.8. Clamp to `[0.05, 0.5]`.

This lives in the driver loop, not in DEAP's algorithm function — DEAP's `eaMuPlusLambda` takes a single `mutpb`. The driver swaps it before each generation:

```
toolbox.unregister("mutate")
toolbox.register("mutate", bounded_mutate, indpb=current_mutpb)
```

Wire in via a small `AdaptiveMutationController` class.

### Niching (genome-distance sharing)

Compute pairwise Hamming-like distance on genomes (with a special weight for the machine gene, since differing-machine candidates are *very* different). For each individual `i`, its shared fitness is:

```
shared_fitness(i) = raw_fitness(i) / sum_j(sharing(d(i, j)))
```

where `sharing(d) = max(0, 1 - d / sigma)` and `sigma` is a threshold (probably `N // 4`). High-fitness clusters get their fitness diluted, so selection picks at least one champion from each cluster.

This is a well-known technique (Goldberg / Richardson 1987); DEAP doesn't ship it but it's ~30 lines. Worth gating behind `--niching` because it can slow convergence when the user actually does want to mode-collapse on a sound.

## Files

Touched:
- `user_interface/voter.py` — add `get_choice(n_options)`
- `genetic/main.py` — `--vote-mode`, `--niching`, `--adaptive-mutation` flags
- `genetic/evaluate.py` — tournament-mode evaluation path
- `genetic/logging.py` — log effective mutation rate per generation (for adaptive case)

New:
- `genetic/diversity.py` — `pairwise_distance()`, `shared_fitness()`, `AdaptiveMutationController`

## Verification

```bash
# Tournament mode
python -m genetic.main run --channel 2 --vote-mode tournament --generations 5
# - Each generation: candidates auditioned in pairs, vote = pad 1 or pad 2
# - Fitness values in votes.jsonl are fractional (0.0, 0.5, 1.0)

# Adaptive mutation
python -m genetic.main run --channel 2 --adaptive-mutation --generations 20
# - mutation_rate column in generations.jsonl varies over the run
# - After 5 generations of flat fitness, rate has increased

# Niching
python -m genetic.main run --channel 2 --niching --generations 10
# - Champion genomes across late generations show >= 2 distinct machine choices
#   even when the user consistently votes 8 on one sonic family
```

Subjective verification matters here too: an hour-long session in tournament mode should feel like exploring a wider sonic space than absolute mode, and an adaptive-mutation run should escape obvious local maxima (e.g. "any kick drum") that flat-rate runs get stuck in.

## Open question

Whether mini-tournament and absolute modes can coexist in the same run — start in absolute, switch to tournament when the population has converged. Plausibly useful, definitely complicates the logging schema. Defer until we know whether either mode alone is good enough.
