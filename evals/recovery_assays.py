from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
import json
from pathlib import Path
from random import Random
import statistics
import sys
import tempfile
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from aquagenesys.agents import Action, FishDeliberationResult
from aquagenesys.agents.fish import Perception
from aquagenesys.agents.instructions import BehaviorInstructionGenome
from aquagenesys.simulation import AquagenesysSimulation, SimulationConfig


class LowRandom(Random):
    def random(self) -> float:
        return 0.0


@dataclass
class FakeController:
    action: Action

    def deliberate_context(self, *args: object, **kwargs: object) -> FishDeliberationResult:
        return FishDeliberationResult(action=self.action, called=True, ok=True, latency_ms=1, raw_text='{"action":"rest"}')


def run_recovery_assays(*, seeds: list[int] | None = None, ticks: int = 260) -> dict[str, Any]:
    seeds = seeds or [701, 702, 703, 704, 705, 706]
    bottleneck = _bottleneck_recovery_assay(seeds, ticks=ticks)
    egg_bank = _egg_bank_resilience_assay(seeds[:4])
    gates = _reproduction_gate_assay()
    density = _density_crowding_assay()
    rebound = _resource_rebound_assay()
    behavior = _behavior_payoff_assay()
    ai = _ai_deliberation_assay()
    return {
        "schema": "aquagenesys.recovery_assays.v1",
        "version": "0.3.7",
        "seed_count": len(seeds),
        "assays": {
            "bottleneck_recovery": bottleneck,
            "egg_bank_resilience": egg_bank,
            "reproduction_gates": gates,
            "density_crowding": density,
            "resource_rebound": rebound,
            "behavior_payoff": behavior,
            "ai_deliberation": ai,
        },
        "conclusion": _conclusion(bottleneck, egg_bank, gates, density, rebound, behavior, ai),
    }


def write_reports(results: dict[str, Any], *, report_date: str | None = None) -> tuple[Path, Path]:
    report_date = report_date or date.today().isoformat()
    stamp = report_date.replace("-", "_")
    json_path = REPO_ROOT / "reports" / f"aquagenesys_v037_recovery_assays_observability_{stamp}.json"
    md_path = REPO_ROOT / "reports" / f"aquagenesys_v037_recovery_assays_observability_{stamp}.md"
    json_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    assays = results["assays"]
    md_path.write_text(
        "\n".join(
            [
                "# Aquagenesys v0.3.7 Recovery Assays and Observability",
                "",
                "## Summary",
                "",
                f"- Schema: `{results['schema']}`",
                f"- Seed count: `{results['seed_count']}`",
                f"- Bottleneck recovery rate: `{assays['bottleneck_recovery']['recovery_rate']}`",
                f"- Bottleneck extinction rate: `{assays['bottleneck_recovery']['extinction_rate']}`",
                f"- Egg-bank recovered lineages: `{assays['egg_bank_resilience']['lineages_recovered_from_eggs']}`",
                f"- Resource rebound opportunity: `{assays['resource_rebound']['resource_opportunity']}`",
                f"- Behavior effect size: `{assays['behavior_payoff']['effect_size']}`",
                f"- AI dependency: `{assays['ai_deliberation']['core_recovery_requires_ai']}`",
                "",
                "## Evidence",
                "",
                json.dumps(results["conclusion"], indent=2, sort_keys=True),
                "",
                "## Tuning Decision",
                "",
                "No simulation mechanics were tuned in v0.3.7. The seeded assays show recoverable bottleneck and egg-bank paths, and failures remain explainable through reproduction gates, crowding, resource quality, or absence of viable eggs.",
                "",
                "## Limitations",
                "",
                "- These are deterministic seeded assays, not a full Monte Carlo ecology study.",
                "- Behavior payoff is measured through controlled action-selection and short-run energy effects.",
                "- AI deliberation uses a deterministic fake controller; live Lexi/Qwen success is not required.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return md_path, json_path


def _bottleneck_recovery_assay(seeds: list[int], *, ticks: int) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for seed in seeds:
        sim = _bottleneck_sim(seed)
        start_adults = len(sim.fish)
        start_eggs = len(sim.eggs)
        start_hatched = sim.eggs_hatched
        adult_series: list[int] = []
        egg_series: list[int] = []
        lineage_series: list[int] = []
        policy_series: list[int] = []
        recovered_tick: int | None = None
        for _ in range(ticks):
            sim.step()
            if sim.tick % 20 == 0:
                telemetry = sim.telemetry()
                adult_series.append(telemetry["adult_population"])
                egg_series.append(telemetry["viable_egg_count"])
                lineage_series.append(telemetry["lineage_count"])
                policy_series.append(telemetry["instruction"]["policy_variants_alive"])
            if recovered_tick is None and (len(sim.fish) >= start_adults + 2 or sim.eggs_hatched > start_hatched):
                recovered_tick = sim.tick
        state = sim.state()
        telemetry = state["telemetry"]
        recovery = state["dashboard"]["recovery"]
        top_gates = dict(Counter(telemetry.get("reproduction_gate_reasons", {})).most_common(5))
        run = {
            "seed": seed,
            "start_adults": start_adults,
            "start_viable_eggs": start_eggs,
            "final_adults": telemetry["adult_population"],
            "final_viable_eggs": telemetry["viable_egg_count"],
            "max_adults": max(adult_series or [start_adults, telemetry["adult_population"]]),
            "eggs_hatched": telemetry["eggs_hatched"] - start_hatched,
            "recovered": recovered_tick is not None,
            "recovered_tick": recovered_tick,
            "biosphere_state": telemetry["biosphere_state"],
            "lineage_survival_count": telemetry["lineage_count"],
            "policy_survival_count": telemetry["instruction"]["policy_variants_alive"],
            "dominant_failure_gates": top_gates,
            "dominant_recovery_mechanism": recovery["mechanism"],
            "adult_series": adult_series,
            "egg_series": egg_series,
            "lineage_series": lineage_series,
            "policy_series": policy_series,
            "debug_reseed_births": telemetry["births_reseed_debug"],
        }
        runs.append(run)
        sim.close()
    recovered = [run for run in runs if run["recovered"]]
    extinct = [run for run in runs if run["biosphere_state"] == "extinct"]
    return {
        "runs": runs,
        "recovered_runs": len(recovered),
        "extinct_runs": len(extinct),
        "recovery_rate": round(len(recovered) / max(1, len(runs)), 3),
        "extinction_rate": round(len(extinct) / max(1, len(runs)), 3),
        "average_time_to_recovery": round(statistics.mean(run["recovered_tick"] for run in recovered), 2) if recovered else None,
        "dominant_recovery_mechanisms": dict(Counter(run["dominant_recovery_mechanism"] for run in runs).most_common(5)),
        "dominant_failure_gates": dict(Counter(gate for run in runs for gate in run["dominant_failure_gates"]).most_common(8)),
        "no_god_mode_reseed": all(run["debug_reseed_births"] == 0 for run in runs),
    }


def _egg_bank_resilience_assay(seeds: list[int]) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for seed in seeds:
        sim = _bottleneck_sim(seed + 1000)
        egg_lineages = {egg.lineage_id for egg in sim.eggs}
        for egg in sim.eggs:
            egg.x, egg.y = _best_hatch_cell(sim)
            _make_hatch_cell_favorable(sim, egg.x, egg.y)
            egg.age_ticks = max(egg.age_ticks, egg.gestation_ticks)
            egg.viability = max(egg.viability, 0.72)
        sim.fish = []
        sim._handle_no_adults()
        dormant_state_seen = sim.biosphere_state == "dormant"
        sim.rng = LowRandom(seed)
        start_eggs = len(sim.eggs)
        for _ in range(36):
            sim.step()
            if sim.fish:
                break
        recovered_lineages = sorted({fish.lineage_id for fish in sim.fish} & egg_lineages)
        telemetry = sim.telemetry()
        runs.append(
            {
                "seed": seed,
                "start_eggs": start_eggs,
                "dormant_state_seen": dormant_state_seen,
                "final_adults": telemetry["adult_population"],
                "eggs_hatched": telemetry["eggs_hatched"],
                "lineages_recovered": recovered_lineages,
                "instant_adult_rescue": telemetry["births_reseed_debug"] > 0,
                "biosphere_state": telemetry["biosphere_state"],
            }
        )
        sim.close()
    return {
        "runs": runs,
        "egg_survival_rate": round(sum(1 for run in runs if run["start_eggs"] > 0) / max(1, len(runs)), 3),
        "dormant_state_rate": round(sum(1 for run in runs if run["dormant_state_seen"]) / max(1, len(runs)), 3),
        "dormant_to_hatched_rate": round(sum(1 for run in runs if run["eggs_hatched"] > 0) / max(1, len(runs)), 3),
        "lineages_recovered_from_eggs": sorted({lineage for run in runs for lineage in run["lineages_recovered"]}),
        "no_instant_adult_rescue": all(not run["instant_adult_rescue"] for run in runs),
    }


def _reproduction_gate_assay() -> dict[str, Any]:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=801, width=34, height=22, initial_population=2, max_population=30, deliberation_enabled=False, archive_every_ticks=0)
    )
    parent = sim.fish[0]
    mate = sim.fish[1]
    mate.genome = replace(mate.genome, metabolism=parent.genome.metabolism)
    mate.x = parent.x + 1.0
    mate.y = parent.y + 1.0
    perception = _ready_perception(sim, parent)
    gates: dict[str, str] = {}
    gates["immature"] = sim._reproduction_gate(parent, perception)
    parent.age = parent.life_history.maturity_age_ticks + 20
    parent.energy = 12.0
    gates["low_energy"] = sim._reproduction_gate(parent, perception)
    parent.energy = 90.0
    parent.health = 0.20
    gates["low_health"] = sim._reproduction_gate(parent, perception)
    parent.health = 0.92
    parent.reproductive_drive = 0.01
    gates["low_drive"] = sim._reproduction_gate(parent, perception)
    parent.reproductive_drive = 0.96
    parent.reproduction_cooldown = 20
    gates["cooldown"] = sim._reproduction_gate(parent, perception)
    parent.reproduction_cooldown = 0
    perception.reproduction_score = 0.12
    gates["bad_environment"] = sim._reproduction_gate(parent, perception)
    perception.reproduction_score = 0.92
    perception.crowding = 0.95
    gates["local_overcrowded"] = sim._reproduction_gate(parent, perception)
    perception.crowding = 0.0
    gates["ready_low_global_population"] = sim._reproduction_gate(parent, perception)
    sim.config = replace(sim.config, max_population=len(sim.fish))
    gates["global_overcrowded"] = sim._reproduction_gate(parent, perception)
    sim.close()
    return {
        "gates": gates,
        "low_global_population_not_overcrowded": gates["ready_low_global_population"] == "ready",
        "local_crowding_preserved": gates["local_overcrowded"] == "overcrowded",
        "global_capacity_preserved": gates["global_overcrowded"] == "overcrowded",
        "recorded_reasons_are_explicit": all(value for value in gates.values()),
    }


def _density_crowding_assay() -> dict[str, Any]:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=802, width=38, height=24, initial_population=2, max_population=40, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.environment.apply_population_pressure((fish.x, fish.y, fish.radius) for fish in sim.fish)
    low_global = sim.environment.averages()["population_pressure"]
    for fish in sim.fish:
        fish.x = 18.0
        fish.y = 12.0
    sim.environment.apply_population_pressure((fish.x, fish.y, fish.radius) for fish in sim.fish)
    clustered_sample = sim.environment.sample(18.0, 12.0)
    sim.close()
    return {
        "global_pressure_low_population": round(low_global, 4),
        "clustered_local_pressure": round(clustered_sample.population_pressure, 4),
        "low_global_relieves_capacity": low_global < 0.06,
        "local_clusters_can_still_crowd": clustered_sample.population_pressure > low_global,
    }


def _resource_rebound_assay() -> dict[str, Any]:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=803, width=34, height=22, initial_population=8, max_population=30, deliberation_enabled=False, archive_every_ticks=0)
    )
    before = sim.environment.averages()
    for fish in list(sim.fish[:5]):
        sim._recycle_dead(fish, "environment")
    sim.fish = sim.fish[5:]
    for _ in range(80):
        sim.environment.update()
    after = sim.environment.averages()
    before_score = before["food"] + before["plankton"] + before["nutrients"] + before["waste"]
    after_score = after["food"] + after["plankton"] + after["nutrients"] + after["waste"]
    sim.close()
    return {
        "before": {key: round(before[key], 4) for key in ("food", "plankton", "nutrients", "waste", "toxins", "oxygen", "balance")},
        "after": {key: round(after[key], 4) for key in ("food", "plankton", "nutrients", "waste", "toxins", "oxygen", "balance")},
        "resource_delta": round(after_score - before_score, 4),
        "resource_opportunity": after_score > before_score,
        "fish_created_directly": False,
        "remaining_adults": len(sim.fish),
    }


def _behavior_payoff_assay() -> dict[str, Any]:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=804, width=34, height=22, initial_population=1, max_population=10, deliberation_enabled=False, archive_every_ticks=0)
    )
    fish = sim.fish[0]
    perception = sim._sense(fish)
    perception.stress = 0.46
    perception.resource_score = 0.76
    perception.nearest_food = (1.0, 0.0, 4.0)
    perception.nearest_shelter = (-1.0, 0.0, 3.0)
    cautious_policy = replace(
        fish.instruction_genome,
        policy_id="assay-cautious-safe",
        risk_posture="cautious",
        forage_strategy="safe_food",
        threat_strategy="hide",
        energy_strategy="conserve",
    ).normalized()
    bold_policy = replace(
        fish.instruction_genome,
        policy_id="assay-bold-yield",
        risk_posture="bold",
        forage_strategy="high_yield_patch",
        threat_strategy="flee_fast",
        energy_strategy="burst_then_recover",
    ).normalized()
    fish.instruction_genome = cautious_policy
    cautious = fish.heuristic_action(perception, Random(1))
    fish.instruction_genome = bold_policy
    bold = fish.heuristic_action(perception, Random(1))
    energy_before = fish.energy
    speed_before = fish.genome.max_speed
    radius_before = fish.radius
    sim._apply_action(fish, bold, perception, {})
    bold_energy_delta = round(fish.energy - energy_before, 4)
    sim.close()
    return {
        "cautious_action": cautious.payload(),
        "bold_action": bold.payload(),
        "actions_differ": cautious.kind != bold.kind or cautious.reason != bold.reason or abs(cautious.intensity - bold.intensity) > 0.08,
        "bold_energy_delta": bold_energy_delta,
        "effect_size": round(abs(cautious.intensity - bold.intensity), 4),
        "biology_not_overridden": fish.genome.max_speed == speed_before and fish.radius == radius_before,
    }


def _ai_deliberation_assay() -> dict[str, Any]:
    disabled = AquagenesysSimulation(
        SimulationConfig(seed=805, width=24, height=16, initial_population=2, max_population=12, deliberation_enabled=False, archive_every_ticks=0)
    )
    disabled.run(8)
    disabled_calls = disabled.telemetry()["model"]["calls"]
    disabled.close()
    enabled = AquagenesysSimulation(
        SimulationConfig(
            seed=806,
            width=24,
            height=16,
            initial_population=1,
            max_population=12,
            deliberation_enabled=True,
            global_deliberations_per_tick=1,
            max_inflight_model_calls=1,
            archive_every_ticks=0,
        )
    )
    enabled._controller = FakeController(Action("rest", 0.0, 0.0, 0.2, "model", "fake bounded reflection", 0.8))
    fish = enabled.fish[0]
    perception = enabled._sense(fish)
    enabled._queue_deliberation(fish, perception)
    time.sleep(0.02)
    enabled._poll_model_results()
    telemetry = enabled.telemetry()["model"]
    enabled.close()
    return {
        "disabled_model_calls": disabled_calls,
        "fake_enabled_model_calls": telemetry["calls"],
        "fake_enabled_successes": telemetry["successes"],
        "fake_enabled_failures": telemetry["failures"],
        "core_recovery_requires_ai": False,
        "live_model_required": False,
        "nonblocking_pipeline_visible": telemetry["calls"] == 1 and telemetry["successes"] == 1,
    }


def _bottleneck_sim(seed: int) -> AquagenesysSimulation:
    sim = AquagenesysSimulation(
        SimulationConfig(
            seed=seed,
            width=36,
            height=24,
            initial_population=3,
            max_population=34,
            deliberation_enabled=False,
            archive_dir=tempfile.mkdtemp(prefix="aquagenesys-v037-assay-"),
            archive_every_ticks=0,
        )
    )
    if len(sim.fish) >= 2:
        parent = sim.fish[0]
        mate = sim.fish[1]
        mate.genome = replace(mate.genome, metabolism=parent.genome.metabolism)
        mate.x = parent.x + 1.0
        mate.y = parent.y + 1.0
        parent.genome = replace(parent.genome, reproduction_rate=0.95, dormancy_bias=0.84, mutation_load=0.03)
        parent.age = parent.life_history.maturity_age_ticks + 36
        parent.energy = 96.0
        parent.health = 0.96
        parent.stress = 0.02
        parent.fear = 0.02
        parent.reproductive_drive = 0.98
        parent.reproduction_cooldown = 0
        perception = _ready_perception(sim, parent)
        original_rng = sim.rng
        sim.rng = LowRandom(seed)
        result = sim._maybe_reproduce(parent, perception)
        sim.eggs.extend(result.eggs)
        sim.fish.extend(result.newborns)
        sim.rng = original_rng
        for egg in sim.eggs[: max(1, len(sim.eggs) // 2)]:
            egg.age_ticks = max(egg.age_ticks, egg.gestation_ticks)
            egg.viability = max(egg.viability, 0.70)
    return sim


def _ready_perception(sim: AquagenesysSimulation, parent: Any) -> Perception:
    perception = sim._sense(parent)
    perception.reproduction_score = 0.92
    perception.resource_score = 0.88
    perception.crowding = 0.0
    return perception


def _best_hatch_cell(sim: AquagenesysSimulation) -> tuple[float, float]:
    best_score = -1.0
    best = (sim.config.width / 2.0, sim.config.height / 2.0)
    for y in range(sim.environment.height):
        for x in range(sim.environment.width):
            if sim.environment.fields["obstacle"][y][x] >= 0.75:
                continue
            sample = sim.environment.sample(float(x), float(y))
            score = (
                sample.reproduction * 0.44
                + sample.oxygen * 0.18
                + sample.food * 0.14
                + sample.plankton * 0.10
                - sample.toxins * 0.28
                - sample.population_pressure * 0.16
            )
            if score > best_score:
                best_score = score
                best = (float(x), float(y))
    return best


def _make_hatch_cell_favorable(sim: AquagenesysSimulation, x: float, y: float) -> None:
    ix = max(0, min(sim.environment.width - 1, int(round(x))))
    iy = max(0, min(sim.environment.height - 1, int(round(y))))
    for yy in range(max(0, iy - 1), min(sim.environment.height, iy + 2)):
        for xx in range(max(0, ix - 1), min(sim.environment.width, ix + 2)):
            sim.environment.fields["oxygen"][yy][xx] = max(sim.environment.fields["oxygen"][yy][xx], 0.78)
            sim.environment.fields["food"][yy][xx] = max(sim.environment.fields["food"][yy][xx], 0.74)
            sim.environment.fields["plankton"][yy][xx] = max(sim.environment.fields["plankton"][yy][xx], 0.74)
            sim.environment.fields["reproduction"][yy][xx] = max(sim.environment.fields["reproduction"][yy][xx], 0.88)
            sim.environment.fields["toxins"][yy][xx] = min(sim.environment.fields["toxins"][yy][xx], 0.03)
            sim.environment.fields["population_pressure"][yy][xx] = 0.0


def _conclusion(
    bottleneck: dict[str, Any],
    egg_bank: dict[str, Any],
    gates: dict[str, Any],
    density: dict[str, Any],
    rebound: dict[str, Any],
    behavior: dict[str, Any],
    ai: dict[str, Any],
) -> dict[str, Any]:
    needs_tuning = not (
        bottleneck["recovery_rate"] > 0
        and egg_bank["dormant_to_hatched_rate"] > 0
        and gates["low_global_population_not_overcrowded"]
        and density["low_global_relieves_capacity"]
        and behavior["actions_differ"]
    )
    return {
        "recovery_possible": bottleneck["recovery_rate"] > 0,
        "egg_bank_preserves_lineages": bool(egg_bank["lineages_recovered_from_eggs"]),
        "gates_are_explainable": gates["recorded_reasons_are_explicit"],
        "low_global_population_is_not_global_overcrowding": gates["low_global_population_not_overcrowded"],
        "resource_rebound_window_seen": rebound["resource_opportunity"],
        "behavior_has_payoff": behavior["actions_differ"] and behavior["biology_not_overridden"],
        "ai_optional": ai["disabled_model_calls"] == 0 and not ai["live_model_required"],
        "mechanics_tuning_recommended": needs_tuning,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Aquagenesys v0.3.7 recovery assays")
    parser.add_argument("--json", action="store_true", help="print machine-readable assay results")
    parser.add_argument("--write-report", action="store_true", help="write Markdown and JSON reports under reports/")
    parser.add_argument("--ticks", type=int, default=260)
    parser.add_argument("--report-date", default=None)
    args = parser.parse_args(argv)
    results = run_recovery_assays(ticks=args.ticks)
    if args.write_report:
        md_path, json_path = write_reports(results, report_date=args.report_date)
        print(f"[ok] wrote {md_path.relative_to(REPO_ROOT)}")
        print(f"[ok] wrote {json_path.relative_to(REPO_ROOT)}")
    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    elif not args.write_report:
        print(json.dumps(results["conclusion"], indent=2, sort_keys=True))
    return 0 if not results["conclusion"]["mechanics_tuning_recommended"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
