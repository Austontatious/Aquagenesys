from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
import time

from dirty_puddle.sim.agents import Cell
from dirty_puddle.sim.fields import EnvironmentalFields


@dataclass(frozen=True)
class WorldSnapshot:
    tick: int
    environment_stage: str
    environment_support_score: float
    effective_mutation_rate: float
    population: int
    organism_count: int
    aquatic_count: int
    biomass_load: float
    births: int
    deaths: int
    mean_energy: float
    mean_age: float
    mean_nutrient_affinity: float
    mean_stress_resistance: float
    nutrient_average: float
    heat_average: float
    toxin_average: float
    lineage_counts: dict[int, int]
    lineage_metrics: dict[int, dict[str, object]]
    colony_count: int
    colony_size_distribution: list[int]
    dominant_colony_lineage: int | None
    colonies: list[dict[str, object]]
    organisms: list[dict[str, object]]
    aquatics: list[dict[str, object]]
    aquatic_metrics: dict[str, object]
    environment_health: dict[str, float]
    extinction_events: int
    speciation_events: int
    collapse_events: int
    mean_adhesion: float
    mean_cooperation: float
    mean_selfishness: float


@dataclass(frozen=True)
class PerformanceSnapshot:
    ticks_per_sec: float
    cells_per_sec: float
    avg_population: float
    max_population: int
    field_update_cost_ms: float
    agent_update_cost_ms: float
    render_cost_ms: float
    metrics_sample_cost_ms: float


class PerformanceTracker:
    def __init__(self) -> None:
        self.started_at = time.perf_counter()
        self.ticks = 0
        self.cell_updates = 0
        self.population_total = 0
        self.max_population = 0
        self.field_updates = 0
        self.render_frames = 0
        self.metric_samples = 0
        self.field_update_seconds = 0.0
        self.agent_update_seconds = 0.0
        self.render_seconds = 0.0
        self.metric_sample_seconds = 0.0

    def record_tick(
        self,
        *,
        population: int,
        field_seconds: float,
        agent_seconds: float,
        metrics_seconds: float,
        metric_sampled: bool,
        field_updated: bool,
    ) -> None:
        self.ticks += 1
        self.cell_updates += population
        self.population_total += population
        if population > self.max_population:
            self.max_population = population
        if field_updated:
            self.field_updates += 1
            self.field_update_seconds += field_seconds
        self.agent_update_seconds += agent_seconds
        if metric_sampled:
            self.metric_samples += 1
            self.metric_sample_seconds += metrics_seconds

    def record_render(self, seconds: float) -> None:
        self.render_frames += 1
        self.render_seconds += seconds

    def snapshot(self) -> PerformanceSnapshot:
        elapsed = max(1.0e-9, time.perf_counter() - self.started_at)
        ticks = max(1, self.ticks)
        return PerformanceSnapshot(
            ticks_per_sec=self.ticks / elapsed,
            cells_per_sec=self.cell_updates / elapsed,
            avg_population=self.population_total / ticks,
            max_population=self.max_population,
            field_update_cost_ms=(self.field_update_seconds / max(1, self.field_updates)) * 1000.0,
            agent_update_cost_ms=(self.agent_update_seconds / ticks) * 1000.0,
            render_cost_ms=(self.render_seconds / max(1, self.render_frames)) * 1000.0,
            metrics_sample_cost_ms=(self.metric_sample_seconds / max(1, self.metric_samples)) * 1000.0,
        )


class MetricsHistory:
    def __init__(self, maxlen: int = 720) -> None:
        self.snapshots: deque[WorldSnapshot] = deque(maxlen=maxlen)

    def append(self, snapshot: WorldSnapshot) -> None:
        self.snapshots.append(snapshot)

    def latest(self) -> WorldSnapshot | None:
        if not self.snapshots:
            return None
        return self.snapshots[-1]

    def populations(self) -> list[int]:
        return [snapshot.population for snapshot in self.snapshots]


def build_snapshot(
    *,
    tick: int,
    environment_stage: str,
    environment_support_score: float,
    effective_mutation_rate: float,
    cells: list[Cell],
    fields: EnvironmentalFields,
    births: int,
    deaths: int,
    lineage_counts: dict[int, int],
    lineage_metrics: dict[int, dict[str, object]],
    colonies: list[dict[str, object]],
    organisms: list[dict[str, object]],
    aquatics: list[dict[str, object]],
    aquatic_metrics: dict[str, object],
    environment_health: dict[str, float],
    colony_size_distribution: list[int],
    dominant_colony_lineage: int | None,
    extinction_events: int,
    speciation_events: int,
    collapse_events: int,
) -> WorldSnapshot:
    population = len(cells)
    if population:
        mean_energy = math.fsum(cell.energy for cell in cells) / population
        mean_age = math.fsum(cell.age for cell in cells) / population
        mean_affinity = math.fsum(cell.genome.nutrient_affinity for cell in cells) / population
        mean_resistance = math.fsum(cell.genome.stress_resistance for cell in cells) / population
        mean_adhesion = math.fsum(cell.genome.adhesion for cell in cells) / population
        mean_cooperation = math.fsum(cell.genome.cooperation for cell in cells) / population
        mean_selfishness = math.fsum(cell.genome.selfishness for cell in cells) / population
    else:
        mean_energy = 0.0
        mean_age = 0.0
        mean_affinity = 0.0
        mean_resistance = 0.0
        mean_adhesion = 0.0
        mean_cooperation = 0.0
        mean_selfishness = 0.0
    nutrient_average, heat_average, toxin_average = fields.averages()
    return WorldSnapshot(
        tick=tick,
        environment_stage=environment_stage,
        environment_support_score=environment_support_score,
        effective_mutation_rate=effective_mutation_rate,
        population=population,
        organism_count=len(organisms),
        aquatic_count=len(aquatics),
        biomass_load=environment_health.get("biomass_load", 0.0),
        births=births,
        deaths=deaths,
        mean_energy=mean_energy,
        mean_age=mean_age,
        mean_nutrient_affinity=mean_affinity,
        mean_stress_resistance=mean_resistance,
        nutrient_average=nutrient_average,
        heat_average=heat_average,
        toxin_average=toxin_average,
        lineage_counts=dict(sorted(lineage_counts.items())),
        lineage_metrics=lineage_metrics,
        colony_count=len(colonies),
        colony_size_distribution=colony_size_distribution,
        dominant_colony_lineage=dominant_colony_lineage,
        colonies=colonies,
        organisms=organisms,
        aquatics=aquatics,
        aquatic_metrics=aquatic_metrics,
        environment_health=environment_health,
        extinction_events=extinction_events,
        speciation_events=speciation_events,
        collapse_events=collapse_events,
        mean_adhesion=mean_adhesion,
        mean_cooperation=mean_cooperation,
        mean_selfishness=mean_selfishness,
    )
