"""Run-directory and JSONL helpers. Pure file I/O — no GA knowledge."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


def make_run_dir(base: Path, pad: int, now: Optional[datetime] = None) -> Path:
    now = now or datetime.now()
    name = f"{now.strftime('%Y-%m-%d-%H%M')}-pad{pad}"
    run_dir = base / name
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def write_config(run_dir: Path, config: dict) -> None:
    (run_dir / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True))


def log_generation(fh, gen, best_fitness, avg_fitness, min_fitness,
                   best_individual, n_evaluated):
    fh.write(json.dumps({
        "gen": gen,
        "best_fitness": best_fitness,
        "avg_fitness": avg_fitness,
        "min_fitness": min_fitness,
        "best_individual": list(best_individual),
        "n_evaluated": n_evaluated,
    }) + "\n")
    fh.flush()


def log_vote(fh, gen, eval_idx, machine, evolved_ccs, fixed_ccs, vote, timestamp_iso):
    fh.write(json.dumps({
        "gen": gen,
        "eval_idx": eval_idx,
        "machine": machine,
        "evolved_ccs": evolved_ccs,
        "fixed_ccs": fixed_ccs,
        "vote": vote,
        "timestamp_iso": timestamp_iso,
    }) + "\n")
    fh.flush()
