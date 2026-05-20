from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import math
from pathlib import Path
import random
import time
from typing import Any

from dirty_puddle.sim.agents import Cell
from dirty_puddle.sim.aquatic import AquaticOrganism, aquatic_from_organism, child_aquatic
from dirty_puddle.sim.colony import ColonyTracker
from dirty_puddle.sim.environment import (
    EnvironmentHealth,
    effective_mutation_rate,
    support_score_from_factors,
)
from dirty_puddle.sim.evolution import (
    child_energy,
    death_probability_values,
    mutated_child_genome,
    stress_mismatch_values,
)
from dirty_puddle.sim.fields import EnvironmentalFields
from dirty_puddle.sim.genome import Genome, average_genome_traits, clamp, founder_genomes
from dirty_puddle.sim.history import EventLog
from dirty_puddle.sim.lineage import LineageTracker
from dirty_puddle.sim.metrics import (
    MetricsHistory,
    PerformanceTracker,
    WorldSnapshot,
    build_snapshot,
)
from dirty_puddle.sim.organisms import MulticellularOrganism, organism_from_colony
from dirty_puddle.sim.stages import EnvironmentStage


CONFIG_ROOT = Path(__file__).resolve().parents[1] / "configs"


@dataclass(frozen=True)
class WorldConfig:
    tier: str = "default_live"
    width: int = 96
    height: int = 64
    seed: int = 7
    initial_cells: int = 90
    max_cells: int = 900
    nutrient_abundance: float = 1.0
    nutrient_regen_rate: float = 0.034
    field_update_interval: int = 6
    volatility: float = 0.24
    mutation_rate: float = 0.035
    mutation_strength: float = 0.075
    stress_pressure: float = 1.35
    reproduction_energy_fraction: float = 0.42
    food_energy_gain: float = 6.2
    base_consume_rate: float = 0.115
    max_age: int = 900
    random_death_chance: float = 0.00035
    metric_history: int = 720
    metric_sample_interval: int = 10
    radiation_level: float = 0.0
    ph_drift: float = 0.0
    salinity_drift: float = 0.0
    temperature_drift: float = 0.0
    mineral_richness: float = 1.0
    predation_pressure: float = 0.15
    reproduction_cost: float = 1.0
    energy_decay: float = 1.0
    random_catastrophe_frequency: float = 0.0
    cooperation_cost: float = 0.035
    cooperation_benefit: float = 0.11
    cooperation_benefit_radius: int = 1
    adhesion_cost: float = 0.026
    adhesion_threshold: float = 0.42
    adhesion_compatibility: float = 0.32
    colony_min_size: int = 3
    colony_stress_protection: float = 0.34
    cheater_advantage: float = 0.45
    speciation_threshold: float = 0.56
    initial_environment_stage: str = EnvironmentStage.COLONY_POND.value
    effective_mutation_min: float = 0.0
    effective_mutation_max: float = 0.45
    stage2_promotion_support: float = 0.42
    stage2_promotion_population: int = 40
    stage2_promotion_ticks: int = 120
    stage2_regression_colony_min: int = 1
    stage2_regression_ticks: int = 500
    stage3_support_threshold: float = 0.54
    stage3_regression_ticks: int = 800
    collapse_support_threshold: float = 0.16
    collapse_ticks: int = 240
    collapse_survivor_fraction: float = 0.20
    multicell_min_colony_size: int = 8
    multicell_min_colony_age: int = 60
    multicell_min_adhesion: float = 0.54
    multicell_min_cooperation: float = 0.30
    multicell_max_cheater_burden: float = 0.42
    multicell_min_energy_surplus: float = 8.0
    multicell_min_lineage_coherence: float = 0.62
    multicell_min_support: float = 0.50
    multicell_promotion_interval: int = 400
    organism_max_age: int = 1600
    organism_reproduction_threshold: float = 70.0
    organism_reproduction_cost: float = 0.48
    organism_min_birth_energy: float = 22.0
    stage4_min_organism_age: int = 260
    stage4_min_lineage_survival: int = 700
    stage4_min_organism_offspring: int = 2
    stage4_min_energy_surplus: float = 42.0
    stage4_min_support: float = 0.58
    stage4_min_movement_speed: float = 0.28
    stage4_min_sensor_score: float = 0.52
    stage4_min_volatility_exposure: float = 40.0
    stage4_min_biodiversity: float = 0.25
    stage4_promotion_interval: int = 800
    stage4_support_threshold: float = 0.50
    stage4_regression_ticks: int = 1400
    aquatic_max_age: int = 2600
    aquatic_reproduction_min_age: int = 80
    aquatic_reproduction_threshold: float = 92.0
    aquatic_reproduction_cost: float = 0.45
    aquatic_min_birth_energy: float = 18.0
    aquatic_degrade_support_threshold: float = 0.32
    event_history_max: int = 2000
    autosave_interval: int = 0

    def normalized(self) -> "WorldConfig":
        stage_values = {stage.value for stage in EnvironmentStage}
        stage = str(self.initial_environment_stage or EnvironmentStage.COLONY_POND.value)
        if stage not in stage_values:
            stage = EnvironmentStage.COLONY_POND.value
        return replace(
            self,
            tier=str(self.tier or "custom"),
            width=max(12, int(self.width)),
            height=max(12, int(self.height)),
            initial_cells=max(3, int(self.initial_cells)),
            max_cells=max(3, int(self.max_cells)),
            nutrient_abundance=clamp(float(self.nutrient_abundance), 0.0, 3.0),
            nutrient_regen_rate=clamp(float(self.nutrient_regen_rate), 0.001, 0.25),
            field_update_interval=max(1, int(self.field_update_interval)),
            volatility=clamp(float(self.volatility), 0.0, 1.5),
            mutation_rate=clamp(float(self.mutation_rate), 0.0, 1.0),
            mutation_strength=clamp(float(self.mutation_strength), 0.0, 0.5),
            stress_pressure=clamp(float(self.stress_pressure), 0.0, 20.0),
            reproduction_energy_fraction=clamp(float(self.reproduction_energy_fraction), 0.1, 0.8),
            food_energy_gain=clamp(float(self.food_energy_gain), 0.1, 20.0),
            base_consume_rate=clamp(float(self.base_consume_rate), 0.01, 1.0),
            max_age=max(50, int(self.max_age)),
            random_death_chance=clamp(float(self.random_death_chance), 0.0, 0.2),
            metric_history=max(60, int(self.metric_history)),
            metric_sample_interval=max(1, int(self.metric_sample_interval)),
            radiation_level=clamp(float(self.radiation_level), 0.0, 3.0),
            ph_drift=clamp(float(self.ph_drift), -1.0, 1.0),
            salinity_drift=clamp(float(self.salinity_drift), -1.0, 1.0),
            temperature_drift=clamp(float(self.temperature_drift), -1.0, 1.0),
            mineral_richness=clamp(float(self.mineral_richness), 0.0, 3.0),
            predation_pressure=clamp(float(self.predation_pressure), 0.0, 3.0),
            reproduction_cost=clamp(float(self.reproduction_cost), 0.25, 3.0),
            energy_decay=clamp(float(self.energy_decay), 0.25, 3.0),
            random_catastrophe_frequency=clamp(float(self.random_catastrophe_frequency), 0.0, 0.2),
            cooperation_cost=clamp(float(self.cooperation_cost), 0.0, 1.0),
            cooperation_benefit=clamp(float(self.cooperation_benefit), 0.0, 2.0),
            cooperation_benefit_radius=max(1, int(self.cooperation_benefit_radius)),
            adhesion_cost=clamp(float(self.adhesion_cost), 0.0, 1.0),
            adhesion_threshold=clamp(float(self.adhesion_threshold), 0.0, 1.0),
            adhesion_compatibility=clamp(float(self.adhesion_compatibility), 0.0, 1.0),
            colony_min_size=max(2, int(self.colony_min_size)),
            colony_stress_protection=clamp(float(self.colony_stress_protection), 0.0, 0.9),
            cheater_advantage=clamp(float(self.cheater_advantage), 0.0, 3.0),
            speciation_threshold=clamp(float(self.speciation_threshold), 0.05, 1.0),
            initial_environment_stage=stage,
            effective_mutation_min=clamp(float(self.effective_mutation_min), 0.0, 1.0),
            effective_mutation_max=clamp(float(self.effective_mutation_max), 0.01, 1.0),
            stage2_promotion_support=clamp(float(self.stage2_promotion_support), 0.0, 1.0),
            stage2_promotion_population=max(1, int(self.stage2_promotion_population)),
            stage2_promotion_ticks=max(1, int(self.stage2_promotion_ticks)),
            stage2_regression_colony_min=max(0, int(self.stage2_regression_colony_min)),
            stage2_regression_ticks=max(1, int(self.stage2_regression_ticks)),
            stage3_support_threshold=clamp(float(self.stage3_support_threshold), 0.0, 1.0),
            stage3_regression_ticks=max(1, int(self.stage3_regression_ticks)),
            collapse_support_threshold=clamp(float(self.collapse_support_threshold), 0.0, 1.0),
            collapse_ticks=max(1, int(self.collapse_ticks)),
            collapse_survivor_fraction=clamp(float(self.collapse_survivor_fraction), 0.01, 1.0),
            multicell_min_colony_size=max(2, int(self.multicell_min_colony_size)),
            multicell_min_colony_age=max(1, int(self.multicell_min_colony_age)),
            multicell_min_adhesion=clamp(float(self.multicell_min_adhesion), 0.0, 1.0),
            multicell_min_cooperation=clamp(float(self.multicell_min_cooperation), 0.0, 1.0),
            multicell_max_cheater_burden=clamp(float(self.multicell_max_cheater_burden), 0.0, 1.0),
            multicell_min_energy_surplus=clamp(float(self.multicell_min_energy_surplus), 0.0, 100.0),
            multicell_min_lineage_coherence=clamp(float(self.multicell_min_lineage_coherence), 0.0, 1.0),
            multicell_min_support=clamp(float(self.multicell_min_support), 0.0, 1.0),
            multicell_promotion_interval=max(1, int(self.multicell_promotion_interval)),
            organism_max_age=max(50, int(self.organism_max_age)),
            organism_reproduction_threshold=clamp(float(self.organism_reproduction_threshold), 5.0, 1000.0),
            organism_reproduction_cost=clamp(float(self.organism_reproduction_cost), 0.1, 0.9),
            organism_min_birth_energy=clamp(float(self.organism_min_birth_energy), 1.0, 500.0),
            stage4_min_organism_age=max(0, int(self.stage4_min_organism_age)),
            stage4_min_lineage_survival=max(0, int(self.stage4_min_lineage_survival)),
            stage4_min_organism_offspring=max(0, int(self.stage4_min_organism_offspring)),
            stage4_min_energy_surplus=clamp(float(self.stage4_min_energy_surplus), 0.0, 1000.0),
            stage4_min_support=clamp(float(self.stage4_min_support), 0.0, 1.0),
            stage4_min_movement_speed=clamp(float(self.stage4_min_movement_speed), 0.0, 2.0),
            stage4_min_sensor_score=clamp(float(self.stage4_min_sensor_score), 0.0, 2.0),
            stage4_min_volatility_exposure=clamp(float(self.stage4_min_volatility_exposure), 0.0, 10000.0),
            stage4_min_biodiversity=clamp(float(self.stage4_min_biodiversity), 0.0, 1.0),
            stage4_promotion_interval=max(1, int(self.stage4_promotion_interval)),
            stage4_support_threshold=clamp(float(self.stage4_support_threshold), 0.0, 1.0),
            stage4_regression_ticks=max(1, int(self.stage4_regression_ticks)),
            aquatic_max_age=max(50, int(self.aquatic_max_age)),
            aquatic_reproduction_min_age=max(1, int(self.aquatic_reproduction_min_age)),
            aquatic_reproduction_threshold=clamp(float(self.aquatic_reproduction_threshold), 5.0, 1000.0),
            aquatic_reproduction_cost=clamp(float(self.aquatic_reproduction_cost), 0.1, 0.9),
            aquatic_min_birth_energy=clamp(float(self.aquatic_min_birth_energy), 1.0, 500.0),
            aquatic_degrade_support_threshold=clamp(float(self.aquatic_degrade_support_threshold), 0.0, 1.0),
            event_history_max=max(100, int(self.event_history_max)),
            autosave_interval=max(0, int(self.autosave_interval)),
        )

    def with_runtime_controls(self, **overrides: float | int | str | None) -> "WorldConfig":
        clean = {
            key: value
            for key, value in overrides.items()
            if value is not None and key in self.__dataclass_fields__
        }
        return replace(self, **clean).normalized()


class World:
    def __init__(
        self,
        config: WorldConfig | None = None,
        *,
        event_log_path: str | None = None,
        checkpoint_path: str | None = None,
        autosave_interval: int | None = None,
    ) -> None:
        self.initial_config = (config or WorldConfig()).normalized()
        self.config = self.initial_config
        self.rng = random.Random(self.config.seed)
        self.tick = 0
        self.next_cell_id = 1
        self.next_organism_id = 1
        self.next_aquatic_id = 1
        self.event_log_path = event_log_path
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else None
        self.autosave_interval = (
            self.config.autosave_interval
            if autosave_interval is None
            else max(0, int(autosave_interval))
        )
        self.fields = EnvironmentalFields(
            self.config.width,
            self.config.height,
            nutrient_abundance=self.config.nutrient_abundance,
            rng=self.rng,
        )
        self._x_by_index = [
            index % self.config.width
            for index in range(self.config.width * self.config.height)
        ]
        self._y_by_index = [
            index // self.config.width
            for index in range(self.config.width * self.config.height)
        ]
        self._neighbor_indices = self._build_neighbor_indices()
        self.lineages = LineageTracker()
        self.colonies = ColonyTracker()
        self.organisms: list[MulticellularOrganism] = []
        self.aquatics: list[AquaticOrganism] = []
        self.environment_stage = EnvironmentStage(self.config.initial_environment_stage)
        self.environment_health = self._default_environment_health()
        self.environment_support_score = self.environment_health.support_score
        self.collapse_events = 0
        self.stage2_good_ticks = 0
        self.stage2_bad_ticks = 0
        self.stage3_bad_ticks = 0
        self.stage4_bad_ticks = 0
        self.collapse_bad_ticks = 0
        self._promoted_colonies: dict[int, int] = {}
        self._promoted_organisms: dict[int, int] = {}
        self._last_extinct_lineages: set[int] = set()
        self._last_dominant_lineage: int | None = None
        self._last_dominant_aquatic_lineage: int | None = None
        self._max_biodiversity = 0
        self.last_aquatic_reproduction_tick = 0
        self.aquatic_predation_events = 0
        self.aquatic_reproduction_events = 0
        self.aquatic_starvation_deaths = 0
        self.aquatic_stress_deaths = 0
        self._aquatic_predation_since_metrics = 0
        self._aquatic_reproduction_since_metrics = 0
        self._aquatic_starvation_since_metrics = 0
        self._aquatic_stress_since_metrics = 0
        self.events = EventLog(maxlen=self.config.event_history_max, jsonl_path=event_log_path)
        self.metrics = MetricsHistory(maxlen=self.config.metric_history)
        self.performance = PerformanceTracker()
        self.cells: list[Cell] = []
        self.total_births = 0
        self.total_deaths = 0
        self.last_births = 0
        self.last_deaths = 0
        self._births_since_metrics = 0
        self._deaths_since_metrics = 0
        self._spawn_initial_cells()
        self._log_event(
            "stage_promotion",
            f"Initial environment stage: {self.environment_stage.value}",
            stage=self.environment_stage.value,
        )
        self._record_metrics(0, 0)

    def reset(self, config: WorldConfig | None = None) -> None:
        self.__init__(
            config or self.initial_config,
            event_log_path=self.event_log_path,
            checkpoint_path=str(self.checkpoint_path) if self.checkpoint_path else None,
            autosave_interval=self.autosave_interval,
        )

    def update_controls(
        self,
        *,
        mutation_rate: float | None = None,
        nutrient_abundance: float | None = None,
        volatility: float | None = None,
        radiation_level: float | None = None,
        ph_drift: float | None = None,
        salinity_drift: float | None = None,
        temperature_drift: float | None = None,
        mineral_richness: float | None = None,
        predation_pressure: float | None = None,
        reproduction_cost: float | None = None,
        energy_decay: float | None = None,
        random_catastrophe_frequency: float | None = None,
        cooperation_cost: float | None = None,
        cooperation_benefit_radius: int | None = None,
        adhesion_cost: float | None = None,
        colony_stress_protection: float | None = None,
        cheater_advantage: float | None = None,
        stage4_min_support: float | None = None,
        aquatic_reproduction_threshold: float | None = None,
        aquatic_reproduction_cost: float | None = None,
        aquatic_degrade_support_threshold: float | None = None,
    ) -> None:
        self.config = self.config.with_runtime_controls(
            mutation_rate=mutation_rate,
            nutrient_abundance=nutrient_abundance,
            volatility=volatility,
            radiation_level=radiation_level,
            ph_drift=ph_drift,
            salinity_drift=salinity_drift,
            temperature_drift=temperature_drift,
            mineral_richness=mineral_richness,
            predation_pressure=predation_pressure,
            reproduction_cost=reproduction_cost,
            energy_decay=energy_decay,
            random_catastrophe_frequency=random_catastrophe_frequency,
            cooperation_cost=cooperation_cost,
            cooperation_benefit_radius=cooperation_benefit_radius,
            adhesion_cost=adhesion_cost,
            colony_stress_protection=colony_stress_protection,
            cheater_advantage=cheater_advantage,
            stage4_min_support=stage4_min_support,
            aquatic_reproduction_threshold=aquatic_reproduction_threshold,
            aquatic_reproduction_cost=aquatic_reproduction_cost,
            aquatic_degrade_support_threshold=aquatic_degrade_support_threshold,
        )

    def add_cell(
        self,
        *,
        genome: Genome,
        x: int,
        y: int,
        energy: float,
        lineage_id: int | None = None,
        parent_id: int | None = None,
    ) -> Cell:
        cell_id = self._next_id()
        if lineage_id is None:
            lineage_id = self.lineages.create_founder(
                founder_id=cell_id,
                genome=genome,
                tick=self.tick,
            )
        else:
            self.lineages.record_birth(lineage_id, self.tick)
        cell = Cell(
            id=cell_id,
            lineage_id=lineage_id,
            parent_id=parent_id,
            genome=genome,
            x=max(0, min(self.config.width - 1, x)),
            y=max(0, min(self.config.height - 1, y)),
            energy=energy,
        )
        self.cells.append(cell)
        return cell

    def run(self, ticks: int) -> WorldSnapshot:
        for _ in range(max(0, ticks)):
            self.step()
        latest = self.metrics.latest()
        if latest is None or latest.tick != self.tick:
            self._record_metrics(self._births_since_metrics, self._deaths_since_metrics)
            self._births_since_metrics = 0
            self._deaths_since_metrics = 0
        latest = self.metrics.latest()
        if latest is None:
            raise RuntimeError("metrics history is empty after run")
        return latest

    def step(self, ticks: int = 1) -> WorldSnapshot:
        latest: WorldSnapshot | None = None
        for _ in range(max(1, ticks)):
            latest = self._step_once()
        if latest is None:
            raise RuntimeError("world step failed to produce metrics")
        return latest

    def summary(self) -> dict[str, Any]:
        latest = self.metrics.latest()
        return {
            "tick": self.tick,
            "environment_stage": self.environment_stage.value,
            "environment_support_score": self.environment_support_score,
            "effective_mutation_rate": self.current_effective_mutation_rate(),
            "population": len(self.cells),
            "organism_count": len(self.organisms),
            "aquatic_count": len(self.aquatics),
            "total_births": self.total_births,
            "total_deaths": self.total_deaths,
            "alive_lineages": self.lineages.alive_lineage_count(),
            "lineage_counts": self.lineage_counts(),
            "events": self.events.to_list(),
            "organisms": [organism.to_dict() for organism in self.organisms],
            "aquatics": [aquatic.to_dict() for aquatic in self.aquatics],
            "aquatic_metrics": self._aquatic_metrics(),
            "config": asdict(self.config),
            "performance": asdict(self.performance.snapshot()),
            "latest": asdict(latest) if latest else None,
        }

    def summary_json(self) -> str:
        return json.dumps(self.summary(), indent=2, sort_keys=True)

    def lineage_counts(self) -> dict[int, int]:
        counts: dict[int, int] = {}
        for cell in self.cells:
            counts[cell.lineage_id] = counts.get(cell.lineage_id, 0) + 1
        return counts

    def _step_once(self) -> WorldSnapshot:
        self.tick += 1
        field_seconds = 0.0
        metrics_seconds = 0.0
        field_updated = self.tick % self.config.field_update_interval == 0
        if field_updated:
            field_start = time.perf_counter()
            self.fields.tick(
                nutrient_regen_rate=min(
                    0.25,
                    self.config.nutrient_regen_rate * self.config.field_update_interval,
                ),
                volatility=self.config.volatility,
                nutrient_abundance=self.config.nutrient_abundance
                * (0.85 + self.config.mineral_richness * 0.15),
                rng=self.rng,
            )
            field_seconds = time.perf_counter() - field_start

        births = 0
        deaths = 0
        agent_start = time.perf_counter()
        width = self.config.width
        occupancy: set[int] = {
            cell.y * width + cell.x for cell in self.cells
        }
        dirty_puddle = self.environment_stage is EnvironmentStage.DIRTY_PUDDLE
        if not dirty_puddle:
            for cell in self.cells:
                cell.reset_social_state()
        survivors: list[Cell] = []
        newborns: list[Cell] = []
        self.rng.shuffle(self.cells)

        for cell in self.cells:
            cell.age += 1
            self._move(cell, occupancy)

        if dirty_puddle:
            self.colonies.active.clear()
        else:
            cell_by_index = {cell.y * width + cell.x: cell for cell in self.cells}
            index_by_cell_id = {cell.id: cell.y * width + cell.x for cell in self.cells}
            previous_colony_count = len(self.colonies.active)
            self.colonies.update(
                cells=self.cells,
                cell_by_index=cell_by_index,
                index_by_cell_id=index_by_cell_id,
                neighbor_indices=self._neighbor_indices,
                tick=self.tick,
                adhesion_threshold=self.config.adhesion_threshold,
                compatibility_threshold=self.config.adhesion_compatibility,
                min_size=self.config.colony_min_size,
            )
            if previous_colony_count == 0 and self.colonies.active:
                self._log_event(
                    "colony_emergence",
                    "Colonies emerged from adhesive cells.",
                    colony_count=len(self.colonies.active),
                )
            self._apply_colony_cooperation(cell_by_index)
            self._promote_stable_colonies()
        catastrophe = self.rng.random() < self.config.random_catastrophe_frequency
        if catastrophe:
            self._log_event(
                "mutation_burst",
                "Random catastrophe created a mutation and selection bottleneck.",
                effective_mutation_rate=self.current_effective_mutation_rate(),
            )

        heat_grid = self.fields.heat
        toxin_grid = self.fields.toxin
        temperature_extra = self.config.temperature_drift * 0.18
        toxin_extra = (
            self.config.radiation_level * 0.05
            + abs(self.config.ph_drift) * 0.05
            + abs(self.config.salinity_drift) * 0.04
        )
        drift_pressure = (
            self.config.radiation_level * 0.42
            + abs(self.config.ph_drift) * 0.28
            + abs(self.config.salinity_drift) * 0.24
            + abs(self.config.temperature_drift) * 0.34
        )
        base_stress_pressure = self.config.stress_pressure + drift_pressure
        mineral_gain = 0.85 + self.config.mineral_richness * 0.15
        food_energy_gain = self.config.food_energy_gain
        consume_rate = self.config.base_consume_rate
        energy_decay = self.config.energy_decay
        adhesion_cost = self.config.adhesion_cost
        max_age = self.config.max_age
        random_death_chance = self.config.random_death_chance
        predation_pressure = self.config.predation_pressure
        max_cells = self.config.max_cells
        rng_random = self.rng.random
        for cell in self.cells:
            genome = cell.genome
            heat = heat_grid[cell.y][cell.x] + temperature_extra
            if heat < 0.0:
                heat = 0.0
            elif heat > 1.0:
                heat = 1.0
            toxin = toxin_grid[cell.y][cell.x] + toxin_extra
            if toxin < 0.0:
                toxin = 0.0
            elif toxin > 1.0:
                toxin = 1.0
            eaten = self.fields.consume(
                cell.x,
                cell.y,
                consume_rate * (0.45 + genome.nutrient_affinity),
            )
            cell.add_energy(
                eaten
                * food_energy_gain
                * mineral_gain
                * (0.65 + genome.nutrient_affinity)
            )
            heat_gap = abs(heat - genome.heat_preference)
            toxin_gap = abs(toxin - genome.toxin_preference)
            stress = (heat_gap + toxin_gap) * 0.5 - genome.stress_resistance * 0.28
            if stress < 0.0:
                stress = 0.0
            elif stress > 1.0:
                stress = 1.0
            stress_pressure = base_stress_pressure * (1.0 - cell.colony_stress_protection)
            if stress_pressure < 0.0:
                stress_pressure = 0.0
            metabolic_cost = (
                (genome.metabolism + genome.mobility * 0.035 + stress * stress_pressure)
                * energy_decay
                + adhesion_cost * genome.adhesion
            )
            cell.spend_energy(metabolic_cost)
            if catastrophe:
                cell.spend_energy((0.45 + self.config.volatility) * (1.0 - cell.colony_stress_protection))

            if cell.energy <= 0.0 or cell.age > max_age * 1.35:
                occupancy.discard(cell.y * width + cell.x)
                self.lineages.record_death(cell.lineage_id, self.tick)
                deaths += 1
                continue
            predation_risk = predation_pressure * 0.0025 * (1.0 - cell.colony_stress_protection)
            old_age = max(0.0, (cell.age - max_age * 0.72) / max(1.0, max_age * 0.28))
            energy_risk = max(0.0, 1.0 - cell.energy / max(0.1, genome.reproduction_threshold))
            death_risk = (
                random_death_chance
                + predation_risk
                + stress * stress * stress_pressure * 0.055
                + old_age * 0.022
                + energy_risk * 0.004
            )
            if death_risk > 0.95:
                death_risk = 0.95
            if rng_random() < death_risk:
                occupancy.discard(cell.y * width + cell.x)
                self.lineages.record_death(cell.lineage_id, self.tick)
                deaths += 1
                continue

            if cell.energy >= genome.reproduction_threshold and len(occupancy) < max_cells:
                child_pos = self._empty_neighbor(cell, occupancy)
                if child_pos is not None:
                    new_cell = self._reproduce(cell, child_pos)
                    occupancy.add(child_pos)
                    newborns.append(new_cell)
                    births += 1

            survivors.append(cell)

        self.cells = survivors + newborns
        self._update_organisms()
        self._promote_aquatic_life()
        self._update_aquatics()
        agent_seconds = time.perf_counter() - agent_start
        self.total_births += births
        self.total_deaths += deaths
        self.last_births = births
        self.last_deaths = deaths
        self._births_since_metrics += births
        self._deaths_since_metrics += deaths
        if deaths > max(8, int(max(1, len(self.cells) + deaths) * 0.18)):
            self._log_event("mass_dieoff", "A mass cell die-off occurred.", deaths=deaths)
        metric_sampled = self.tick % self.config.metric_sample_interval == 0
        if metric_sampled:
            metrics_start = time.perf_counter()
            latest = self._record_metrics(
                self._births_since_metrics,
                self._deaths_since_metrics,
            )
            self._births_since_metrics = 0
            self._deaths_since_metrics = 0
            metrics_seconds = time.perf_counter() - metrics_start
        else:
            latest = self.metrics.latest()
            if latest is None:
                latest = self._record_metrics(0, 0)
                metric_sampled = True
        self.performance.record_tick(
            population=len(self.cells),
            field_seconds=field_seconds,
            agent_seconds=agent_seconds,
            metrics_seconds=metrics_seconds,
            metric_sampled=metric_sampled,
            field_updated=field_updated,
        )
        self._maybe_autosave()
        return latest

    def _dies(self, cell: Cell, heat: float, toxin: float) -> bool:
        if cell.energy <= 0.0:
            return True
        if cell.age > self.config.max_age * 1.35:
            return True
        predation_risk = self.config.predation_pressure * 0.0025 * (1.0 - cell.colony_stress_protection)
        probability = death_probability_values(
            cell,
            heat,
            toxin,
            stress_pressure=self._effective_stress_pressure(cell),
            max_age=self.config.max_age,
            random_death_chance=self.config.random_death_chance + predation_risk,
        )
        return self.rng.random() < probability

    def _move(self, cell: Cell, occupancy: set[int]) -> None:
        genome = cell.genome
        adhesion_drag = genome.adhesion * (0.48 - genome.selfishness * 0.14)
        effective_mobility = genome.mobility * (1.0 - adhesion_drag)
        if effective_mobility < 0.02:
            effective_mobility = 0.02
        elif effective_mobility > 1.0:
            effective_mobility = 1.0
        rng_random = self.rng.random
        if rng_random() > effective_mobility:
            return
        width = self.config.width
        current = cell.y * width + cell.x
        best_pos = current
        nutrient_grid = self.fields.nutrient
        heat_grid = self.fields.heat
        toxin_grid = self.fields.toxin
        heat_preference = genome.heat_preference
        toxin_preference = genome.toxin_preference
        stress_resistance = genome.stress_resistance
        nutrient_affinity = genome.nutrient_affinity
        heat_gap = abs(heat_grid[cell.y][cell.x] - heat_preference)
        toxin_gap = abs(toxin_grid[cell.y][cell.x] - toxin_preference)
        stress = (heat_gap + toxin_gap) * 0.5 - stress_resistance * 0.28
        if stress < 0.0:
            stress = 0.0
        elif stress > 1.0:
            stress = 1.0
        best_score = nutrient_grid[cell.y][cell.x] * nutrient_affinity - stress * 0.95
        x_by_index = self._x_by_index
        y_by_index = self._y_by_index
        for index in self._neighbor_indices[current]:
            if index in occupancy:
                continue
            x = x_by_index[index]
            y = y_by_index[index]
            heat_gap = abs(heat_grid[y][x] - heat_preference)
            toxin_gap = abs(toxin_grid[y][x] - toxin_preference)
            stress = (heat_gap + toxin_gap) * 0.5 - stress_resistance * 0.28
            if stress < 0.0:
                stress = 0.0
            elif stress > 1.0:
                stress = 1.0
            score = nutrient_grid[y][x] * nutrient_affinity - stress * 0.95 + rng_random() * 0.025
            if score > best_score:
                best_pos = index
                best_score = score
        if best_pos != current:
            occupancy.discard(current)
            occupancy.add(best_pos)
            cell.x = x_by_index[best_pos]
            cell.y = y_by_index[best_pos]

    def _site_score(self, cell: Cell, x: int, y: int) -> float:
        nutrient = self.fields.nutrient[y][x]
        heat = self.fields.heat[y][x]
        toxin = self.fields.toxin[y][x]
        return (
            nutrient * cell.genome.nutrient_affinity
            - stress_mismatch_values(cell.genome, heat, toxin) * 0.95
        )

    def _reproduce(self, parent: Cell, pos: int) -> Cell:
        energy = child_energy(parent, self.config.reproduction_energy_fraction)
        parent.spend_energy(energy * self.config.reproduction_cost)
        child_id = self._next_id()
        child_genome = mutated_child_genome(
            parent,
            self.rng,
            mutation_rate=self.current_effective_mutation_rate(),
            mutation_strength=self.config.mutation_strength,
        )
        lineage_id = parent.lineage_id
        founder_genome = self.lineages.records[parent.lineage_id].founder_genome_to_genome()
        if child_genome.distance(founder_genome) >= self.config.speciation_threshold:
            lineage_id = self.lineages.create_split(
                founder_id=child_id,
                parent_lineage_id=parent.lineage_id,
                genome=child_genome,
                tick=self.tick,
            )
        else:
            self.lineages.record_birth(lineage_id, self.tick)
        child = Cell(
            id=child_id,
            lineage_id=lineage_id,
            parent_id=parent.id,
            genome=child_genome,
            x=self._x_by_index[pos],
            y=self._y_by_index[pos],
            energy=energy,
        )
        return child

    def _apply_colony_cooperation(self, cell_by_index: dict[int, Cell]) -> None:
        if not self.colonies.active:
            return
        width = self.config.width
        radius = self.config.cooperation_benefit_radius
        contribution_by_cell_id: dict[int, float] = {}
        for cell in self.cells:
            contribution = cell.genome.cooperation * (1.0 - cell.genome.selfishness)
            if contribution <= 0.0 or cell.colony_id is None:
                contribution_by_cell_id[cell.id] = 0.0
                continue
            paid = self.config.cooperation_cost * contribution
            cell.spend_energy(paid)
            cell.cooperation_paid += paid
            contribution_by_cell_id[cell.id] = contribution

        for cell in self.cells:
            if cell.colony_id is None:
                continue
            local_contribution = 0.0
            local_shielding = 0.0
            local_count = 0
            for y in range(max(0, cell.y - radius), min(self.config.height, cell.y + radius + 1)):
                row = y * width
                for x in range(max(0, cell.x - radius), min(self.config.width, cell.x + radius + 1)):
                    other = cell_by_index.get(row + x)
                    if other is None or other.colony_id != cell.colony_id:
                        continue
                    local_count += 1
                    local_contribution += contribution_by_cell_id.get(other.id, 0.0)
                    local_shielding += other.genome.stress_shielding * (
                        1.0 - other.genome.selfishness * 0.5
                    )
            if local_count <= 0:
                continue
            benefit = (
                self.config.cooperation_benefit
                * local_contribution
                / local_count
                * (1.0 + cell.genome.selfishness * self.config.cheater_advantage)
            )
            cell.add_energy(benefit)
            cell.public_good_received += benefit
            colony = self.colonies.active[cell.colony_id]
            colony_size_bonus = min(0.12, colony.size * 0.006)
            protection = (
                cell.genome.adhesion * 0.12
                + local_shielding / local_count * 0.32
                + colony_size_bonus
            )
            cell.colony_stress_protection = min(self.config.colony_stress_protection, protection)

    def _effective_stress_pressure(self, cell: Cell) -> float:
        drift_pressure = (
            self.config.radiation_level * 0.42
            + abs(self.config.ph_drift) * 0.28
            + abs(self.config.salinity_drift) * 0.24
            + abs(self.config.temperature_drift) * 0.34
        )
        pressure = self.config.stress_pressure + drift_pressure
        return max(0.0, pressure * (1.0 - cell.colony_stress_protection))

    def current_effective_mutation_rate(self) -> float:
        return effective_mutation_rate(
            base_mutation_rate=self.config.mutation_rate,
            radiation_level=self.config.radiation_level,
            volatility=self.config.volatility,
            random_catastrophe_frequency=self.config.random_catastrophe_frequency,
            ph_drift=self.config.ph_drift,
            salinity_drift=self.config.salinity_drift,
            temperature_drift=self.config.temperature_drift,
            minimum=self.config.effective_mutation_min,
            maximum=self.config.effective_mutation_max,
        )

    def _promote_stable_colonies(self) -> None:
        if self.environment_stage is EnvironmentStage.DIRTY_PUDDLE:
            return
        if self.environment_support_score < self.config.multicell_min_support:
            return
        for colony in list(self.colonies.active.values()):
            last_promoted = self._promoted_colonies.get(colony.colony_id, -10**9)
            if self.tick - last_promoted < self.config.multicell_promotion_interval:
                continue
            if not self._colony_meets_multicell_thresholds(colony):
                continue
            members = [cell for cell in self.cells if cell.colony_id == colony.colony_id]
            if not members:
                continue
            energy = sum(cell.energy for cell in members) * 0.30
            for cell in members:
                cell.spend_energy(cell.energy * 0.10)
            organism = organism_from_colony(
                organism_id=self.next_organism_id,
                origin_colony_id=colony.colony_id,
                origin_lineage_id=colony.dominant_lineage,
                x=max(0, min(self.config.width - 1, int(round(colony.centroid[0])))),
                y=max(0, min(self.config.height - 1, int(round(colony.centroid[1])))),
                body_size=colony.size,
                energy=max(self.config.organism_min_birth_energy, energy),
                traits=colony.average_traits,
                max_age=self.config.organism_max_age,
            )
            self.next_organism_id += 1
            self.organisms.append(organism)
            self._promoted_colonies[colony.colony_id] = self.tick
            if self.environment_stage is not EnvironmentStage.MULTICELLULAR_POND:
                self._set_environment_stage(
                    EnvironmentStage.MULTICELLULAR_POND,
                    "stage_promotion",
                    "Stable colony promoted the world to multicellular pond life.",
                    organism_id=organism.organism_id,
                    colony_id=colony.colony_id,
                )
            self._log_event(
                "multicellular_emergence",
                "A stable colony became a simple multicellular organism.",
                organism_id=organism.organism_id,
                colony_id=colony.colony_id,
                lineage_id=organism.origin_lineage_id,
                body_size=organism.body_size,
            )

    def _colony_meets_multicell_thresholds(self, colony: Any) -> bool:
        if colony.size < self.config.multicell_min_colony_size:
            return False
        if colony.age < self.config.multicell_min_colony_age:
            return False
        traits = colony.average_traits
        if traits.get("adhesion", 0.0) < self.config.multicell_min_adhesion:
            return False
        if colony.cooperation_rate < self.config.multicell_min_cooperation:
            return False
        if colony.cheater_rate > self.config.multicell_max_cheater_burden:
            return False
        dominant = colony.lineage_mix.get(colony.dominant_lineage, 0) / max(1, colony.size)
        if dominant < self.config.multicell_min_lineage_coherence:
            return False
        members = [cell for cell in self.cells if cell.colony_id == colony.colony_id]
        if not members:
            return False
        mean_energy = sum(cell.energy for cell in members) / len(members)
        return mean_energy >= self.config.multicell_min_energy_surplus

    def _update_organisms(self) -> tuple[int, int]:
        if not self.organisms:
            return 0, 0
        births = 0
        deaths = 0
        survivors: list[MulticellularOrganism] = []
        for organism in self.organisms:
            organism.age += 1
            self._move_organism(organism)
            nutrient = self.fields.consume(
                organism.x,
                organism.y,
                min(0.7, 0.06 + organism.body_size * 0.012),
            )
            organism.add_energy(
                nutrient
                * self.config.food_energy_gain
                * (0.7 + organism.sensor_profile["nutrient"])
                * (0.8 + self.config.mineral_richness * 0.12)
            )
            heat = clamp(self.fields.heat[organism.y][organism.x] + self.config.temperature_drift * 0.18, 0.0, 1.0)
            toxin = clamp(
                self.fields.toxin[organism.y][organism.x]
                + self.config.radiation_level * 0.05
                + abs(self.config.ph_drift) * 0.05
                + abs(self.config.salinity_drift) * 0.04,
                0.0,
                1.0,
            )
            stress = abs(heat - 0.48) + toxin + self.config.predation_pressure * 0.12
            organism.spend_energy(
                organism.metabolism
                * self.config.energy_decay
                + max(0.0, stress - organism.stress_tolerance) * 0.18
            )
            organism.reproductive_readiness = organism.energy / max(1.0, self.config.organism_reproduction_threshold)
            if self._organism_dies(organism, stress):
                deaths += 1
                self._log_event(
                    "organism_death",
                    "A multicellular organism died.",
                    organism_id=organism.organism_id,
                    lineage_id=organism.origin_lineage_id,
                )
                continue
            if organism.ready_to_reproduce(self.config.organism_reproduction_threshold):
                child = self._reproduce_organism(organism)
                if child is not None:
                    births += 1
                    survivors.append(child)
            survivors.append(organism)
        self.organisms = survivors
        return births, deaths

    def _move_organism(self, organism: MulticellularOrganism) -> None:
        if self.rng.random() > organism.movement_speed:
            return
        current = self._index(organism.x, organism.y)
        best = current
        best_score = self._organism_site_score(organism, organism.x, organism.y)
        for index in self._neighbor_indices[current]:
            x = self._x_by_index[index]
            y = self._y_by_index[index]
            score = self._organism_site_score(organism, x, y)
            if score > best_score:
                best = index
                best_score = score
        organism.x = self._x_by_index[best]
        organism.y = self._y_by_index[best]

    def _organism_site_score(self, organism: MulticellularOrganism, x: int, y: int) -> float:
        nutrient = self.fields.nutrient[y][x] * organism.sensor_profile["nutrient"]
        stress = (
            abs(self.fields.heat[y][x] - 0.48)
            + self.fields.toxin[y][x]
        ) * organism.sensor_profile["stress"]
        crowding = sum(
            1
            for other in self.organisms
            if other.organism_id != organism.organism_id
            and abs(other.x - x) <= 1
            and abs(other.y - y) <= 1
        )
        return nutrient - stress - crowding * organism.sensor_profile["crowding"] * 0.18

    def _organism_dies(self, organism: MulticellularOrganism, stress: float) -> bool:
        if organism.energy <= 0.0:
            return True
        if organism.age > organism.max_age:
            return True
        death_risk = (
            self.config.random_death_chance
            + self.config.predation_pressure * 0.0018
            + max(0.0, stress - organism.stress_tolerance) * 0.006
            + self.config.radiation_level * 0.0015
        )
        return self.rng.random() < death_risk

    def _reproduce_organism(self, parent: MulticellularOrganism) -> MulticellularOrganism | None:
        if parent.energy < self.config.organism_reproduction_threshold:
            return None
        parent.spend_energy(parent.energy * self.config.organism_reproduction_cost)
        pos = self._empty_neighbor_index(parent.x, parent.y)
        if pos is None:
            return None
        child = MulticellularOrganism(
            organism_id=self.next_organism_id,
            origin_colony_id=parent.origin_colony_id,
            origin_lineage_id=parent.origin_lineage_id,
            age=0,
            energy=max(self.config.organism_min_birth_energy, parent.energy * 0.35),
            x=self._x_by_index[pos],
            y=self._y_by_index[pos],
            body_size=max(3, int(parent.body_size * 0.72)),
            movement_speed=parent.movement_speed,
            metabolism=parent.metabolism,
            stress_tolerance=parent.stress_tolerance,
            cooperation_profile=dict(parent.cooperation_profile),
            cheater_burden=parent.cheater_burden,
            reproductive_readiness=0.0,
            sensor_profile=dict(parent.sensor_profile),
            feeding_strategy=parent.feeding_strategy,
            max_age=parent.max_age,
        )
        parent.offspring_count += 1
        self.next_organism_id += 1
        self._log_event(
            "organism_reproduction",
            "A multicellular organism spawned a juvenile.",
            parent_id=parent.organism_id,
            organism_id=child.organism_id,
            lineage_id=child.origin_lineage_id,
        )
        return child

    def _promote_aquatic_life(self) -> None:
        if self.environment_stage not in {
            EnvironmentStage.MULTICELLULAR_POND,
            EnvironmentStage.AQUATIC_ECOSYSTEM,
        }:
            return
        if self.environment_support_score < self.config.stage4_min_support:
            return
        for organism in list(self.organisms):
            last_promoted = self._promoted_organisms.get(organism.organism_id, -10**9)
            if self.tick - last_promoted < self.config.stage4_promotion_interval:
                continue
            if not self._organism_meets_aquatic_thresholds(organism):
                continue
            record = self.lineages.records.get(organism.origin_lineage_id)
            color = record.color if record else (120, 205, 235)
            aquatic = aquatic_from_organism(
                aquatic_id=self.next_aquatic_id,
                organism=organism,
                reproduction_threshold=self.config.aquatic_reproduction_threshold,
                max_age=self.config.aquatic_max_age,
                rng=self.rng,
                color_marker=color,
            )
            self.next_aquatic_id += 1
            self.aquatics.append(aquatic)
            self._promoted_organisms[organism.organism_id] = self.tick
            organism.spend_energy(organism.energy * 0.24)
            if self.environment_stage is not EnvironmentStage.AQUATIC_ECOSYSTEM:
                self._set_environment_stage(
                    EnvironmentStage.AQUATIC_ECOSYSTEM,
                    "stage_promotion",
                    "Stable multicellular life promoted the world to aquatic ecosystem.",
                    aquatic_id=aquatic.aquatic_id,
                    organism_id=organism.organism_id,
                )
            self._log_event(
                "aquatic_emergence",
                "A mature multicellular organism became free-moving aquatic life.",
                aquatic_id=aquatic.aquatic_id,
                organism_id=organism.organism_id,
                lineage_id=aquatic.origin_lineage_id,
                body_size=aquatic.body_size,
            )

    def _organism_meets_aquatic_thresholds(self, organism: MulticellularOrganism) -> bool:
        if organism.age < self.config.stage4_min_organism_age:
            return False
        if organism.offspring_count < self.config.stage4_min_organism_offspring:
            return False
        if organism.energy < self.config.stage4_min_energy_surplus:
            return False
        if organism.movement_speed < self.config.stage4_min_movement_speed:
            return False
        sensor_score = (
            organism.sensor_profile.get("nutrient", 0.0)
            + organism.sensor_profile.get("stress", 0.0)
            + organism.sensor_profile.get("crowding", 0.0)
        ) / 3.0
        if sensor_score < self.config.stage4_min_sensor_score:
            return False
        volatility_exposure = organism.age * max(0.10, self.config.volatility)
        if volatility_exposure < self.config.stage4_min_volatility_exposure:
            return False
        if self._biodiversity_stability_score() < self.config.stage4_min_biodiversity:
            return False
        record = self.lineages.records.get(organism.origin_lineage_id)
        lineage_survival = self.tick - record.birth_tick if record else 0
        return lineage_survival >= self.config.stage4_min_lineage_survival

    def _update_aquatics(self) -> tuple[int, int]:
        if not self.aquatics:
            return 0, 0
        births = 0
        deaths = 0
        eaten_aquatic_ids: set[int] = set()
        eaten_organism_ids: set[int] = set()
        newborns: list[AquaticOrganism] = []
        survivors: list[AquaticOrganism] = []
        for aquatic in self.aquatics:
            if aquatic.aquatic_id in eaten_aquatic_ids:
                continue
            aquatic.age += 1
            self._move_aquatic(aquatic)
            self._feed_aquatic(aquatic)
            self._aquatic_predation(aquatic, eaten_aquatic_ids, eaten_organism_ids)
            stress = self._aquatic_stress(aquatic)
            aquatic.spend_energy(
                aquatic.metabolism * self.config.energy_decay
                + max(0.0, stress - aquatic.stress_tolerance) * 0.24
            )
            cause = self._aquatic_death_cause(aquatic, stress)
            if cause is not None:
                deaths += 1
                if cause == "starvation":
                    self.aquatic_starvation_deaths += 1
                    self._aquatic_starvation_since_metrics += 1
                elif cause == "stress":
                    self.aquatic_stress_deaths += 1
                    self._aquatic_stress_since_metrics += 1
                self._log_event(
                    "aquatic_death",
                    "A free-moving aquatic organism died.",
                    aquatic_id=aquatic.aquatic_id,
                    lineage_id=aquatic.origin_lineage_id,
                    cause=cause,
                )
                continue
            if aquatic.ready_to_reproduce(self.config.aquatic_reproduction_min_age):
                child = self._reproduce_aquatic(aquatic)
                if child is not None:
                    births += 1
                    newborns.append(child)
            survivors.append(aquatic)
        if eaten_organism_ids:
            self.organisms = [
                organism
                for organism in self.organisms
                if organism.organism_id not in eaten_organism_ids
            ]
        self.aquatics = survivors + newborns
        return births, deaths

    def _move_aquatic(self, aquatic: AquaticOrganism) -> None:
        target_x, target_y = self._best_aquatic_target(aquatic)
        desired_x = target_x - aquatic.x
        desired_y = target_y - aquatic.y
        desired_length = math.hypot(desired_x, desired_y)
        if desired_length > 0.0001:
            desired_x /= desired_length
            desired_y /= desired_length
        desired_vx = desired_x * aquatic.movement_speed
        desired_vy = desired_y * aquatic.movement_speed
        aquatic.vx += (desired_vx - aquatic.vx) * aquatic.turn_rate
        aquatic.vy += (desired_vy - aquatic.vy) * aquatic.turn_rate
        velocity = math.hypot(aquatic.vx, aquatic.vy)
        if velocity > aquatic.movement_speed:
            scale = aquatic.movement_speed / velocity
            aquatic.vx *= scale
            aquatic.vy *= scale
        aquatic.x += aquatic.vx
        aquatic.y += aquatic.vy
        if aquatic.x < 0.0:
            aquatic.x = 0.0
            aquatic.vx = abs(aquatic.vx) * 0.45
        elif aquatic.x > self.config.width - 1:
            aquatic.x = float(self.config.width - 1)
            aquatic.vx = -abs(aquatic.vx) * 0.45
        if aquatic.y < 0.0:
            aquatic.y = 0.0
            aquatic.vy = abs(aquatic.vy) * 0.45
        elif aquatic.y > self.config.height - 1:
            aquatic.y = float(self.config.height - 1)
            aquatic.vy = -abs(aquatic.vy) * 0.45

    def _best_aquatic_target(self, aquatic: AquaticOrganism) -> tuple[float, float]:
        cx = int(round(aquatic.x))
        cy = int(round(aquatic.y))
        radius = max(1, aquatic.sensory_radius)
        step = 1 if radius <= 4 else 2
        best_x = cx
        best_y = cy
        best_score = -10**9
        preferred_heat = aquatic.preferred_environment_profile.get("heat", 0.48)
        preferred_toxin = aquatic.preferred_environment_profile.get("toxin", 0.2)
        for y in range(max(0, cy - radius), min(self.config.height, cy + radius + 1), step):
            for x in range(max(0, cx - radius), min(self.config.width, cx + radius + 1), step):
                nutrient = self.fields.nutrient[y][x]
                stress = (
                    abs(self.fields.heat[y][x] - preferred_heat)
                    + max(0.0, self.fields.toxin[y][x] - preferred_toxin)
                )
                crowding = sum(
                    1
                    for other in self.aquatics
                    if other.aquatic_id != aquatic.aquatic_id
                    and abs(other.x - x) <= 2.0
                    and abs(other.y - y) <= 2.0
                )
                prey_score = self._aquatic_prey_score(aquatic, float(x), float(y))
                flee_score = self._aquatic_flee_score(aquatic, float(x), float(y))
                score = nutrient * 1.2 + prey_score - stress * 1.4 - crowding * 0.18 - flee_score
                if score > best_score:
                    best_score = score
                    best_x = x
                    best_y = y
        return float(best_x), float(best_y)

    def _aquatic_prey_score(self, aquatic: AquaticOrganism, x: float, y: float) -> float:
        if aquatic.aggression < 0.20:
            return 0.0
        score = 0.0
        for prey in self.aquatics:
            if prey.aquatic_id == aquatic.aquatic_id or prey.body_size >= aquatic.body_size * 0.88:
                continue
            distance = math.hypot(prey.x - x, prey.y - y)
            if distance <= aquatic.sensory_radius:
                score += aquatic.aggression * (1.0 - distance / max(1.0, aquatic.sensory_radius)) * 0.7
        for organism in self.organisms:
            if organism.body_size >= aquatic.body_size * 1.15:
                continue
            distance = math.hypot(organism.x - x, organism.y - y)
            if distance <= aquatic.sensory_radius:
                score += aquatic.aggression * 0.35
        return score

    def _aquatic_flee_score(self, aquatic: AquaticOrganism, x: float, y: float) -> float:
        pressure = 0.0
        for other in self.aquatics:
            if other.aquatic_id == aquatic.aquatic_id:
                continue
            if other.body_size <= aquatic.body_size * 1.15 or other.aggression <= aquatic.defense:
                continue
            distance = math.hypot(other.x - x, other.y - y)
            if distance <= aquatic.sensory_radius:
                pressure += (other.aggression - aquatic.defense) * (1.0 - distance / max(1.0, aquatic.sensory_radius))
        return max(0.0, pressure)

    def _feed_aquatic(self, aquatic: AquaticOrganism) -> None:
        x = max(0, min(self.config.width - 1, int(round(aquatic.x))))
        y = max(0, min(self.config.height - 1, int(round(aquatic.y))))
        amount = min(1.2, 0.08 + aquatic.body_size * 0.018)
        nutrient = self.fields.consume(x, y, amount)
        aquatic.add_energy(
            nutrient
            * self.config.food_energy_gain
            * (0.75 + self.config.mineral_richness * 0.10)
        )

    def _aquatic_predation(
        self,
        predator: AquaticOrganism,
        eaten_aquatic_ids: set[int],
        eaten_organism_ids: set[int],
    ) -> None:
        if predator.aggression < 0.25:
            return
        for prey in self.aquatics:
            if prey.aquatic_id == predator.aquatic_id or prey.aquatic_id in eaten_aquatic_ids:
                continue
            if prey.body_size >= predator.body_size * 0.86:
                continue
            if math.hypot(prey.x - predator.x, prey.y - predator.y) > max(1.6, predator.body_size * 0.12):
                continue
            odds = predator.aggression + predator.body_size * 0.01 - prey.defense
            if odds > self.rng.random() * 0.85:
                eaten_aquatic_ids.add(prey.aquatic_id)
                predator.add_energy(prey.body_size * (1.4 + predator.aggression))
                self.aquatic_predation_events += 1
                self._aquatic_predation_since_metrics += 1
                self._log_event(
                    "aquatic_predation",
                    "An aquatic organism consumed smaller prey.",
                    predator_id=predator.aquatic_id,
                    prey_id=prey.aquatic_id,
                    lineage_id=predator.origin_lineage_id,
                )
                return
        for organism in self.organisms:
            if organism.organism_id in eaten_organism_ids:
                continue
            if organism.body_size >= predator.body_size * 1.20:
                continue
            if math.hypot(organism.x - predator.x, organism.y - predator.y) > max(1.4, predator.body_size * 0.10):
                continue
            odds = predator.aggression + predator.body_size * 0.006 - organism.stress_tolerance * 0.45
            if odds > self.rng.random() * 0.95:
                eaten_organism_ids.add(organism.organism_id)
                predator.add_energy(organism.body_size * 0.75)
                self.aquatic_predation_events += 1
                self._aquatic_predation_since_metrics += 1
                self._log_event(
                    "aquatic_predation",
                    "An aquatic organism consumed multicellular prey.",
                    predator_id=predator.aquatic_id,
                    organism_id=organism.organism_id,
                    lineage_id=predator.origin_lineage_id,
                )
                return

    def _aquatic_stress(self, aquatic: AquaticOrganism) -> float:
        x = max(0, min(self.config.width - 1, int(round(aquatic.x))))
        y = max(0, min(self.config.height - 1, int(round(aquatic.y))))
        preferred = aquatic.preferred_environment_profile
        heat = clamp(self.fields.heat[y][x] + self.config.temperature_drift * 0.18, 0.0, 1.0)
        toxin = clamp(
            self.fields.toxin[y][x]
            + self.config.radiation_level * 0.05
            + abs(self.config.ph_drift) * 0.05
            + abs(self.config.salinity_drift) * 0.04,
            0.0,
            1.0,
        )
        return (
            abs(heat - preferred.get("heat", 0.48))
            + max(0.0, toxin - preferred.get("toxin", 0.2))
            + self.config.predation_pressure * 0.10
        )

    def _aquatic_death_cause(self, aquatic: AquaticOrganism, stress: float) -> str | None:
        if aquatic.energy <= 0.0:
            return "starvation"
        if aquatic.age > aquatic.max_age:
            return "age"
        stress_risk = max(0.0, stress - aquatic.stress_tolerance) * 0.010 + self.config.radiation_level * 0.0015
        if self.rng.random() < stress_risk:
            return "stress"
        return None

    def _reproduce_aquatic(self, parent: AquaticOrganism) -> AquaticOrganism | None:
        if parent.energy < parent.reproduction_threshold:
            return None
        parent.spend_energy(parent.energy * self.config.aquatic_reproduction_cost)
        angle = self.rng.random() * math.tau
        distance = max(1.0, parent.body_size * 0.08)
        x = clamp(parent.x + math.cos(angle) * distance, 0.0, float(self.config.width - 1))
        y = clamp(parent.y + math.sin(angle) * distance, 0.0, float(self.config.height - 1))
        child = child_aquatic(
            aquatic_id=self.next_aquatic_id,
            parent=parent,
            x=x,
            y=y,
            rng=self.rng,
        )
        child.energy = max(self.config.aquatic_min_birth_energy, child.energy)
        self.next_aquatic_id += 1
        parent.offspring_count += 1
        self.aquatic_reproduction_events += 1
        self._aquatic_reproduction_since_metrics += 1
        self.last_aquatic_reproduction_tick = self.tick
        self._log_event(
            "aquatic_reproduction",
            "A free-moving aquatic organism spawned a juvenile.",
            parent_id=parent.aquatic_id,
            aquatic_id=child.aquatic_id,
            lineage_id=child.origin_lineage_id,
        )
        return child

    def _empty_neighbor_index(self, x: int, y: int) -> int | None:
        candidates = self._neighbor_indices[self._index(x, y)]
        if not candidates:
            return None
        occupied = {organism.y * self.config.width + organism.x for organism in self.organisms}
        start = self.rng.randrange(len(candidates))
        for offset in range(len(candidates)):
            index = candidates[(start + offset) % len(candidates)]
            if index not in occupied:
                return index
        return None

    def _empty_neighbor(
        self,
        cell: Cell,
        occupancy: set[int],
    ) -> int | None:
        candidates = self._neighbor_indices[cell.y * self.config.width + cell.x]
        start = self.rng.randrange(len(candidates)) if candidates else 0
        for offset in range(len(candidates)):
            index = candidates[(start + offset) % len(candidates)]
            if index not in occupancy:
                return index
        return None

    def _build_neighbor_indices(self) -> list[tuple[int, ...]]:
        return [
            tuple(self._index(nx, ny) for nx, ny in self._neighbors(x, y))
            for y in range(self.config.height)
            for x in range(self.config.width)
        ]

    def _neighbors(self, x: int, y: int) -> tuple[tuple[int, int], ...]:
        candidates = [
            (x - 1, y),
            (x + 1, y),
            (x, y - 1),
            (x, y + 1),
            (x - 1, y - 1),
            (x + 1, y + 1),
        ]
        return tuple(
            (nx, ny)
            for nx, ny in candidates
            if 0 <= nx < self.config.width and 0 <= ny < self.config.height
        )

    def _index(self, x: int, y: int) -> int:
        return y * self.config.width + x

    def _xy(self, index: int) -> tuple[int, int]:
        return index % self.config.width, index // self.config.width

    def _spawn_initial_cells(self) -> None:
        genomes = founder_genomes()
        per_lineage = max(1, self.config.initial_cells // len(genomes))
        occupied: set[tuple[int, int]] = set()
        for lineage_index, genome in enumerate(genomes):
            founder = self._spawn_founder(lineage_index, genome, occupied)
            for _ in range(per_lineage - 1):
                pos = self._initial_position(lineage_index, occupied)
                child_genome = genome.mutated(
                    self.rng,
                    mutation_rate=min(0.45, self.current_effective_mutation_rate() * 1.5),
                    mutation_strength=self.config.mutation_strength * 0.55,
                )
                self.add_cell(
                    genome=child_genome,
                    x=pos[0],
                    y=pos[1],
                    energy=self.rng.uniform(7.0, 11.5),
                    lineage_id=founder.lineage_id,
                    parent_id=founder.id,
                )
                occupied.add(pos)

        extra = self.config.initial_cells - per_lineage * len(genomes)
        for i in range(max(0, extra)):
            lineage_index = i % len(genomes)
            lineage_id = lineage_index + 1
            pos = self._initial_position(lineage_index, occupied)
            self.add_cell(
                genome=genomes[lineage_index],
                x=pos[0],
                y=pos[1],
                energy=self.rng.uniform(7.0, 11.5),
                lineage_id=lineage_id,
                parent_id=None,
            )
            occupied.add(pos)

    def _spawn_founder(
        self,
        lineage_index: int,
        genome: Genome,
        occupied: set[tuple[int, int]],
    ) -> Cell:
        cell_id = self._next_id()
        lineage_id = self.lineages.create_founder(
            founder_id=cell_id,
            genome=genome,
            tick=self.tick,
        )
        pos = self._initial_position(lineage_index, occupied)
        cell = Cell(
            id=cell_id,
            lineage_id=lineage_id,
            parent_id=None,
            genome=genome,
            x=pos[0],
            y=pos[1],
            energy=self.rng.uniform(8.5, 12.5),
        )
        self.cells.append(cell)
        occupied.add(pos)
        return cell

    def _initial_position(
        self,
        lineage_index: int,
        occupied: set[tuple[int, int]],
    ) -> tuple[int, int]:
        if lineage_index == 0:
            x_low, x_high = 1, max(2, int(self.config.width * 0.30))
        elif lineage_index == 1:
            x_low, x_high = int(self.config.width * 0.70), self.config.width - 2
        else:
            x_low, x_high = int(self.config.width * 0.40), int(self.config.width * 0.60)
        for _ in range(250):
            x = self.rng.randint(max(0, x_low), max(0, x_high))
            y = self.rng.randint(1, max(1, self.config.height - 2))
            if (x, y) not in occupied:
                return (x, y)
        for y in range(self.config.height):
            for x in range(self.config.width):
                if (x, y) not in occupied:
                    return (x, y)
        raise RuntimeError("no open cell positions remain")

    def _default_environment_health(self) -> EnvironmentHealth:
        return EnvironmentHealth(
            nutrient_regeneration_capacity=0.5,
            toxin_waste_load=0.35,
            oxygen_light_mineral_availability=0.5,
            ph_stability=1.0,
            salinity_stability=1.0,
            temperature_stability=1.0,
            radiation_stress=0.0,
            biodiversity=0.3,
            biomass_load=0.0,
            extinction_pressure=0.0,
            colony_stability=0.0,
            organism_survival=0.0,
            support_score=0.5,
        )

    def _calculate_environment_health(self, *, births: int, deaths: int) -> EnvironmentHealth:
        nutrient_avg, _heat_avg, toxin_avg = self.fields.averages()
        capacity = self.config.width * self.config.height
        organism_biomass = sum(organism.body_size for organism in self.organisms)
        aquatic_biomass = sum(aquatic.body_size for aquatic in self.aquatics)
        biomass_load = clamp(
            (len(self.cells) + organism_biomass * 2.5 + aquatic_biomass * 5.0)
            / max(1.0, capacity * 0.24),
            0.0,
            2.0,
        )
        lineage_count = max(1, self.lineages.alive_lineage_count())
        aquatic_lineages = len(self._aquatic_lineage_counts())
        biodiversity = clamp(
            (lineage_count + min(4, len(self.organisms)) * 0.5 + min(4, aquatic_lineages) * 0.75)
            / 8.0,
            0.0,
            1.0,
        )
        extinction_pressure = clamp((deaths / max(1, len(self.cells) + deaths)) + self.lineages.extinction_events * 0.002, 0.0, 1.0)
        colony_sizes = self.colonies.size_distribution()
        if colony_sizes:
            colony_stability = clamp(
                (len(colony_sizes) / 12.0)
                + (sum(colony_sizes[:5]) / max(1, len(self.cells))) * 0.35
                - self._mean_colony_cheater_burden() * 0.18,
                0.0,
                1.0,
            )
        else:
            colony_stability = 0.0
        organism_survival = clamp((len(self.organisms) + len(self.aquatics) * 0.8) / 8.0, 0.0, 1.0)
        nutrient_regeneration_capacity = clamp(
            self.config.nutrient_abundance * self.config.nutrient_regen_rate * 8.0 * (0.5 + self.config.mineral_richness * 0.5),
            0.0,
            1.0,
        )
        toxin_waste_load = clamp(
            toxin_avg * 0.65
            + biomass_load * 0.18
            + (aquatic_biomass / max(1.0, capacity)) * 0.18
            + self.config.radiation_level * 0.10
            + abs(self.config.ph_drift) * 0.05
            + abs(self.config.salinity_drift) * 0.04,
            0.0,
            1.0,
        )
        oxygen_light_mineral = clamp(
            0.34 + nutrient_avg * 0.18 + self.config.mineral_richness * 0.28 - biomass_load * 0.10,
            0.0,
            1.0,
        )
        ph_stability = 1.0 - abs(self.config.ph_drift)
        salinity_stability = 1.0 - abs(self.config.salinity_drift)
        temperature_stability = 1.0 - abs(self.config.temperature_drift)
        radiation_stress = clamp(self.config.radiation_level / 2.0, 0.0, 1.0)
        support = support_score_from_factors(
            nutrient_regeneration_capacity=nutrient_regeneration_capacity,
            toxin_waste_load=toxin_waste_load,
            oxygen_light_mineral_availability=oxygen_light_mineral,
            ph_stability=ph_stability,
            salinity_stability=salinity_stability,
            temperature_stability=temperature_stability,
            radiation_stress=radiation_stress,
            biodiversity=biodiversity,
            biomass_load=biomass_load,
            extinction_pressure=extinction_pressure,
            colony_stability=colony_stability,
            organism_survival=organism_survival,
        )
        return EnvironmentHealth(
            nutrient_regeneration_capacity=nutrient_regeneration_capacity,
            toxin_waste_load=toxin_waste_load,
            oxygen_light_mineral_availability=oxygen_light_mineral,
            ph_stability=ph_stability,
            salinity_stability=salinity_stability,
            temperature_stability=temperature_stability,
            radiation_stress=radiation_stress,
            biodiversity=biodiversity,
            biomass_load=biomass_load,
            extinction_pressure=extinction_pressure,
            colony_stability=colony_stability,
            organism_survival=organism_survival,
            support_score=support,
        )

    def _mean_colony_cheater_burden(self) -> float:
        if not self.colonies.active:
            return 0.0
        return sum(colony.cheater_rate for colony in self.colonies.active.values()) / len(self.colonies.active)

    def _aquatic_lineage_counts(self) -> dict[int, int]:
        counts: dict[int, int] = {}
        for aquatic in self.aquatics:
            counts[aquatic.origin_lineage_id] = counts.get(aquatic.origin_lineage_id, 0) + 1
        return counts

    def _dominant_aquatic_lineage(self) -> int | None:
        counts = self._aquatic_lineage_counts()
        if not counts:
            return None
        return max(counts.items(), key=lambda item: item[1])[0]

    def _aquatic_biodiversity(self) -> float:
        if not self.aquatics:
            return 0.0
        return clamp(len(self._aquatic_lineage_counts()) / max(1, len(self.lineages.records)), 0.0, 1.0)

    def _biodiversity_stability_score(self) -> float:
        cell_lineages = len([count for count in self.lineage_counts().values() if count > 0])
        organism_lineages = len({organism.origin_lineage_id for organism in self.organisms})
        aquatic_lineages = len(self._aquatic_lineage_counts())
        return clamp((cell_lineages + organism_lineages * 0.8 + aquatic_lineages) / 6.0, 0.0, 1.0)

    def _aquatic_metrics(self) -> dict[str, object]:
        count = len(self.aquatics)
        if not count:
            return {
                "aquatic_count": 0,
                "aquatic_lineage_counts": {},
                "average_speed": 0.0,
                "average_body_size": 0.0,
                "average_aggression": 0.0,
                "average_defense": 0.0,
                "predation_events": self.aquatic_predation_events,
                "reproduction_events": self.aquatic_reproduction_events,
                "starvation_deaths": self.aquatic_starvation_deaths,
                "stress_deaths": self.aquatic_stress_deaths,
                "trophic_pressure": 0.0,
                "aquatic_biodiversity": 0.0,
                "dominant_aquatic_lineage": None,
            }
        average_speed = sum(math.hypot(aquatic.vx, aquatic.vy) for aquatic in self.aquatics) / count
        average_body_size = sum(aquatic.body_size for aquatic in self.aquatics) / count
        average_aggression = sum(aquatic.aggression for aquatic in self.aquatics) / count
        average_defense = sum(aquatic.defense for aquatic in self.aquatics) / count
        trophic_pressure = clamp(
            self._aquatic_predation_since_metrics / max(1, count + self._aquatic_reproduction_since_metrics),
            0.0,
            1.0,
        )
        return {
            "aquatic_count": count,
            "aquatic_lineage_counts": self._aquatic_lineage_counts(),
            "average_speed": average_speed,
            "average_body_size": average_body_size,
            "average_aggression": average_aggression,
            "average_defense": average_defense,
            "predation_events": self.aquatic_predation_events,
            "reproduction_events": self.aquatic_reproduction_events,
            "starvation_deaths": self.aquatic_starvation_deaths,
            "stress_deaths": self.aquatic_stress_deaths,
            "trophic_pressure": trophic_pressure,
            "aquatic_biodiversity": self._aquatic_biodiversity(),
            "dominant_aquatic_lineage": self._dominant_aquatic_lineage(),
        }

    def _evaluate_stage_transitions(self) -> None:
        support = self.environment_support_score
        if support <= self.config.collapse_support_threshold:
            self.collapse_bad_ticks += self.config.metric_sample_interval
        else:
            self.collapse_bad_ticks = 0
        if self.collapse_bad_ticks >= self.config.collapse_ticks:
            self._trigger_dirty_puddle_collapse("Environment health fell below collapse threshold.")
            return

        if self.environment_stage is EnvironmentStage.DIRTY_PUDDLE:
            if support >= self.config.stage2_promotion_support and len(self.cells) >= self.config.stage2_promotion_population:
                self.stage2_good_ticks += self.config.metric_sample_interval
            else:
                self.stage2_good_ticks = 0
            if self.stage2_good_ticks >= self.config.stage2_promotion_ticks:
                self._set_environment_stage(
                    EnvironmentStage.COLONY_POND,
                    "stage_promotion",
                    "Dirty puddle recovered into microbiome colony pond.",
                    support_score=support,
                )
                self.stage2_good_ticks = 0
            return

        if self.environment_stage is EnvironmentStage.COLONY_POND:
            cheater_burden = self._mean_colony_cheater_burden()
            unstable = (
                len(self.colonies.active) < self.config.stage2_regression_colony_min
                or support < self.config.stage2_promotion_support * 0.55
                or cheater_burden > 0.82
            )
            if unstable:
                self.stage2_bad_ticks += self.config.metric_sample_interval
            else:
                self.stage2_bad_ticks = 0
            if self.stage2_bad_ticks >= self.config.stage2_regression_ticks:
                self._regress_to_dirty_puddle(
                    "Colony ecology destabilized and regressed to dirty puddle.",
                    cheater_burden=cheater_burden,
                    support_score=support,
                )
            return

        if self.environment_stage is EnvironmentStage.AQUATIC_ECOSYSTEM:
            if support < self.config.aquatic_degrade_support_threshold and self.aquatics:
                self._degrade_aquatic_life(
                    "Low environment support degraded aquatic life first.",
                    support_score=support,
                )
            stagnant = (
                not self.aquatics
                or support < self.config.stage4_support_threshold
                or self.tick - self.last_aquatic_reproduction_tick > self.config.stage4_regression_ticks
            )
            if stagnant:
                self.stage4_bad_ticks += self.config.metric_sample_interval
            else:
                self.stage4_bad_ticks = 0
            if self.stage4_bad_ticks >= self.config.stage4_regression_ticks:
                self._regress_to_multicellular_pond(
                    "Aquatic ecosystem failed to remain established.",
                    support_score=support,
                    aquatic_count=len(self.aquatics),
                )
            return

        if self.environment_stage is EnvironmentStage.MULTICELLULAR_POND:
            stagnant = not self.organisms or support < self.config.stage3_support_threshold
            if stagnant:
                self.stage3_bad_ticks += self.config.metric_sample_interval
            else:
                self.stage3_bad_ticks = 0
            if self.stage3_bad_ticks >= self.config.stage3_regression_ticks:
                self._regress_to_colony_pond("Multicellular life failed to remain established.", support_score=support)

    def _set_environment_stage(
        self,
        stage: EnvironmentStage,
        event_kind: str,
        message: str,
        **data: Any,
    ) -> None:
        if self.environment_stage is stage:
            return
        previous = self.environment_stage.value
        self.environment_stage = stage
        self._log_event(event_kind, message, previous_stage=previous, stage=stage.value, **data)

    def _regress_to_colony_pond(self, message: str, **data: Any) -> None:
        self.aquatics.clear()
        self.organisms = [
            organism
            for organism in self.organisms
            if organism.energy > self.config.organism_min_birth_energy * 1.4 and self.rng.random() < 0.35
        ]
        self._set_environment_stage(EnvironmentStage.COLONY_POND, "stage_regression", message, **data)
        self.stage3_bad_ticks = 0
        self.stage4_bad_ticks = 0

    def _regress_to_multicellular_pond(self, message: str, **data: Any) -> None:
        self._degrade_aquatic_life(message, severe=True, **data)
        self._set_environment_stage(EnvironmentStage.MULTICELLULAR_POND, "stage_regression", message, **data)
        self.stage4_bad_ticks = 0

    def _degrade_aquatic_life(self, message: str, *, severe: bool = False, **data: Any) -> None:
        if not self.aquatics:
            return
        survivors: list[AquaticOrganism] = []
        for aquatic in self.aquatics:
            survival_chance = 0.20 if severe else 0.55
            if aquatic.energy > self.config.aquatic_min_birth_energy * 1.25 and self.rng.random() < survival_chance:
                aquatic.spend_energy(aquatic.energy * (0.35 if severe else 0.18))
                survivors.append(aquatic)
            else:
                self._log_event(
                    "aquatic_collapse",
                    "Unsupported aquatic life died back.",
                    aquatic_id=aquatic.aquatic_id,
                    lineage_id=aquatic.origin_lineage_id,
                    **data,
                )
        self.aquatics = survivors
        self._log_event(
            "aquatic_collapse",
            message,
            survivors=len(self.aquatics),
            severe=severe,
            **data,
        )

    def _regress_to_dirty_puddle(self, message: str, **data: Any) -> None:
        self.aquatics.clear()
        self.organisms.clear()
        self.colonies.active.clear()
        for cell in self.cells:
            cell.colony_id = None
            cell.spend_energy(cell.energy * 0.18)
        self._set_environment_stage(EnvironmentStage.DIRTY_PUDDLE, "stage_regression", message, **data)
        self.stage2_bad_ticks = 0

    def _trigger_dirty_puddle_collapse(self, message: str) -> None:
        self.collapse_events += 1
        self.organisms.clear()
        self.aquatics.clear()
        survivor_count = max(3, int(len(self.cells) * self.config.collapse_survivor_fraction))
        self.rng.shuffle(self.cells)
        survivors = self.cells[:survivor_count]
        for cell in survivors:
            cell.energy = max(1.0, cell.energy * 0.45)
            cell.colony_id = None
        for cell in self.cells[survivor_count:]:
            self.lineages.record_death(cell.lineage_id, self.tick)
        self.cells = survivors
        self.colonies.active.clear()
        self.environment_stage = EnvironmentStage.DIRTY_PUDDLE
        self.collapse_bad_ticks = 0
        self.stage2_bad_ticks = 0
        self.stage3_bad_ticks = 0
        self.stage4_bad_ticks = 0
        self._log_event(
            "environmental_collapse",
            message,
            stage=self.environment_stage.value,
            survivors=len(self.cells),
            collapse_events=self.collapse_events,
        )

    def _record_timeline_events(self, *, births: int, deaths: int) -> None:
        current_extinct = {
            lineage_id
            for lineage_id, record in self.lineages.records.items()
            if record.alive == 0
        }
        for lineage_id in sorted(current_extinct - self._last_extinct_lineages):
            self._log_event("lineage_extinction", "A lineage went extinct.", lineage_id=lineage_id)
        self._last_extinct_lineages = current_extinct

        counts = self.lineage_counts()
        if counts:
            dominant, count = max(counts.items(), key=lambda item: item[1])
            if dominant != self._last_dominant_lineage and count / max(1, len(self.cells)) >= 0.55:
                self._log_event("lineage_dominance", "A lineage became dominant.", lineage_id=dominant, share=count / max(1, len(self.cells)))
                self._last_dominant_lineage = dominant
        biodiversity = self.lineages.alive_lineage_count()
        if biodiversity > self._max_biodiversity:
            self._max_biodiversity = biodiversity
            self._log_event("biodiversity_peak", "Biodiversity reached a new peak.", alive_lineages=biodiversity)
        aquatic_counts = self._aquatic_lineage_counts()
        if aquatic_counts:
            aquatic_dominant, aquatic_count = max(aquatic_counts.items(), key=lambda item: item[1])
            if (
                aquatic_dominant != self._last_dominant_aquatic_lineage
                and aquatic_count / max(1, len(self.aquatics)) >= 0.55
            ):
                self._log_event(
                    "aquatic_lineage_dominance",
                    "An aquatic lineage became dominant.",
                    lineage_id=aquatic_dominant,
                    share=aquatic_count / max(1, len(self.aquatics)),
                )
                self._last_dominant_aquatic_lineage = aquatic_dominant
        if births > max(12, deaths * 2) and births > len(self.cells) * 0.08:
            self._log_event("recovery_bloom", "A recovery bloom increased population.", births=births, deaths=deaths)
        if self._mean_colony_cheater_burden() > 0.75 and len(self.colonies.active) <= 1:
            self._log_event("cheater_collapse", "High cheater burden destabilized colonies.", cheater_burden=self._mean_colony_cheater_burden())
        if self.current_effective_mutation_rate() > self.config.mutation_rate * 1.8:
            self._log_event(
                "mutation_burst",
                "Environmental pressure raised effective mutation rate.",
                effective_mutation_rate=self.current_effective_mutation_rate(),
            )

    def _log_event(self, kind: str, message: str, **data: Any) -> None:
        self.events.add(tick=self.tick, kind=kind, message=message, **data)

    def _maybe_autosave(self) -> None:
        if not self.checkpoint_path or self.autosave_interval <= 0:
            return
        if self.tick > 0 and self.tick % self.autosave_interval == 0:
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            self.checkpoint_path.write_text(
                json.dumps(self.export_history(), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            self._log_event("checkpoint", "Autosave checkpoint written.", path=str(self.checkpoint_path))

    def export_history(self) -> dict[str, Any]:
        return {
            "config": asdict(self.config),
            "seed": self.config.seed,
            "tick": self.tick,
            "stage": self.environment_stage.value,
            "events": self.events.to_list(),
            "metrics": [asdict(snapshot) for snapshot in self.metrics.snapshots],
            "lineage_summaries": self._lineage_metrics(),
            "organisms": [organism.to_dict() for organism in self.organisms],
            "aquatics": [aquatic.to_dict() for aquatic in self.aquatics],
            "aquatic_metrics": self._aquatic_metrics(),
            "collapse_events": self.collapse_events,
        }

    def _record_metrics(self, births: int, deaths: int) -> WorldSnapshot:
        self.lineages.reconcile_alive(self.lineage_counts(), self.tick)
        self.environment_health = self._calculate_environment_health(births=births, deaths=deaths)
        self.environment_support_score = self.environment_health.support_score
        self._evaluate_stage_transitions()
        self._record_timeline_events(births=births, deaths=deaths)
        colonies = [colony.to_dict() for colony in self.colonies.active.values()]
        organisms = [organism.to_dict() for organism in self.organisms]
        aquatics = [aquatic.to_dict() for aquatic in self.aquatics]
        aquatic_metrics = self._aquatic_metrics()
        snapshot = build_snapshot(
            tick=self.tick,
            environment_stage=self.environment_stage.value,
            environment_support_score=self.environment_support_score,
            effective_mutation_rate=self.current_effective_mutation_rate(),
            cells=self.cells,
            fields=self.fields,
            births=births,
            deaths=deaths,
            lineage_counts=self.lineage_counts(),
            lineage_metrics=self._lineage_metrics(),
            colonies=colonies,
            organisms=organisms,
            aquatics=aquatics,
            aquatic_metrics=aquatic_metrics,
            environment_health=self.environment_health.to_dict(),
            colony_size_distribution=self.colonies.size_distribution(),
            dominant_colony_lineage=self.colonies.dominant_colony_lineage(),
            extinction_events=self.lineages.extinction_events,
            speciation_events=self.lineages.speciation_events,
            collapse_events=self.collapse_events,
        )
        self.metrics.append(snapshot)
        self._aquatic_predation_since_metrics = 0
        self._aquatic_reproduction_since_metrics = 0
        self._aquatic_starvation_since_metrics = 0
        self._aquatic_stress_since_metrics = 0
        return snapshot

    def _lineage_metrics(self) -> dict[int, dict[str, object]]:
        cells_by_lineage: dict[int, list[Cell]] = {}
        colonies_by_lineage: dict[int, set[int]] = {}
        organism_count_by_lineage: dict[int, int] = {}
        aquatic_count_by_lineage: dict[int, int] = {}
        for cell in self.cells:
            cells_by_lineage.setdefault(cell.lineage_id, []).append(cell)
            if cell.colony_id is not None:
                colonies_by_lineage.setdefault(cell.lineage_id, set()).add(cell.colony_id)
        for organism in self.organisms:
            lineage_id = organism.origin_lineage_id
            organism_count_by_lineage[lineage_id] = organism_count_by_lineage.get(lineage_id, 0) + 1
        for aquatic in self.aquatics:
            lineage_id = aquatic.origin_lineage_id
            aquatic_count_by_lineage[lineage_id] = aquatic_count_by_lineage.get(lineage_id, 0) + 1

        metrics: dict[int, dict[str, object]] = {}
        for lineage_id, record in self.lineages.records.items():
            lineage_cells = cells_by_lineage.get(lineage_id, [])
            population = len(lineage_cells)
            if population:
                mean_energy = sum(cell.energy for cell in lineage_cells) / population
                cooperation_rate = sum(cell.genome.cooperation for cell in lineage_cells) / population
                cheating_rate = sum(cell.genome.selfishness for cell in lineage_cells) / population
                survival_time = self.tick - record.birth_tick
            else:
                mean_energy = 0.0
                cooperation_rate = 0.0
                cheating_rate = 0.0
                survival_time = record.last_seen_tick - record.birth_tick
            metrics[lineage_id] = {
                "population": population,
                "survival_time": max(0, survival_time),
                "mean_energy": mean_energy,
                "average_traits": average_genome_traits(lineage_cells),
                "cooperation_rate": cooperation_rate,
                "cheating_rate": cheating_rate,
                "colony_count": len(colonies_by_lineage.get(lineage_id, set())),
                "organism_count": organism_count_by_lineage.get(lineage_id, 0),
                "aquatic_count": aquatic_count_by_lineage.get(lineage_id, 0),
                "births": record.births,
                "deaths": record.deaths,
                "extinct": population == 0,
                "child_lineages": list(record.children),
            }
        return metrics

    def record_render_cost(self, seconds: float) -> None:
        self.performance.record_render(seconds)

    def _next_id(self) -> int:
        cell_id = self.next_cell_id
        self.next_cell_id += 1
        return cell_id


def load_world_config(config: str | Path | None = None) -> WorldConfig:
    path = _resolve_config_path(config or "default")
    payload = _load_flat_yaml(path)
    valid_fields = set(WorldConfig.__dataclass_fields__.keys())
    unknown = sorted(set(payload) - valid_fields)
    if unknown:
        raise ValueError(f"unknown config keys in {path}: {', '.join(unknown)}")
    return WorldConfig(**payload).normalized()


def _resolve_config_path(config: str | Path) -> Path:
    raw = Path(config)
    if raw.exists():
        return raw
    name = raw.name
    if raw.suffix != ".yaml":
        name = f"{name}.yaml"
    candidate = CONFIG_ROOT / name
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"config not found: {config}")


def _load_flat_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"{path}:{line_number}: expected 'key: value'")
        key, value = line.split(":", 1)
        data[key.strip()] = _parse_scalar(value.strip())
    return data


def _parse_scalar(value: str) -> Any:
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        if any(marker in value for marker in (".", "e", "E")):
            return float(value)
        return int(value)
    except ValueError:
        return value.strip('"').strip("'")
