from __future__ import annotations

import random

from dirty_puddle.sim.agents import Cell
from dirty_puddle.sim.fields import FieldSample
from dirty_puddle.sim.genome import Genome, clamp


def stress_mismatch(genome: Genome, sample: FieldSample) -> float:
    return stress_mismatch_values(genome, sample.heat, sample.toxin)


def stress_mismatch_values(genome: Genome, heat: float, toxin: float) -> float:
    heat_gap = abs(heat - genome.heat_preference)
    toxin_gap = abs(toxin - genome.toxin_preference)
    raw = (heat_gap + toxin_gap) * 0.5
    value = raw - genome.stress_resistance * 0.28
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def metabolic_cost(cell: Cell, sample: FieldSample, *, stress_pressure: float) -> float:
    return metabolic_cost_values(cell, sample.heat, sample.toxin, stress_pressure=stress_pressure)


def metabolic_cost_values(
    cell: Cell,
    heat: float,
    toxin: float,
    *,
    stress_pressure: float,
) -> float:
    stress = stress_mismatch_values(cell.genome, heat, toxin)
    motion_cost = cell.genome.mobility * 0.035
    return cell.genome.metabolism + motion_cost + stress * stress_pressure


def death_probability(
    cell: Cell,
    sample: FieldSample,
    *,
    stress_pressure: float,
    max_age: int,
    random_death_chance: float,
) -> float:
    return death_probability_values(
        cell,
        sample.heat,
        sample.toxin,
        stress_pressure=stress_pressure,
        max_age=max_age,
        random_death_chance=random_death_chance,
    )


def death_probability_values(
    cell: Cell,
    heat: float,
    toxin: float,
    *,
    stress_pressure: float,
    max_age: int,
    random_death_chance: float,
) -> float:
    stress = stress_mismatch_values(cell.genome, heat, toxin)
    old_age = max(0.0, (cell.age - max_age * 0.72) / max(1.0, max_age * 0.28))
    energy_risk = max(0.0, 1.0 - cell.energy / max(0.1, cell.genome.reproduction_threshold))
    value = (
        random_death_chance
        + stress * stress * stress_pressure * 0.055
        + old_age * 0.022
        + energy_risk * 0.004
    )
    if value < 0.0:
        return 0.0
    if value > 0.95:
        return 0.95
    return value


def can_reproduce(cell: Cell) -> bool:
    return cell.energy >= cell.genome.reproduction_threshold


def child_energy(parent: Cell, fraction: float) -> float:
    return max(2.0, parent.energy * clamp(fraction, 0.1, 0.8))


def mutated_child_genome(
    parent: Cell,
    rng: random.Random,
    *,
    mutation_rate: float,
    mutation_strength: float,
) -> Genome:
    return parent.genome.mutated(
        rng,
        mutation_rate=mutation_rate,
        mutation_strength=mutation_strength,
    )
