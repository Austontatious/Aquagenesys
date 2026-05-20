from __future__ import annotations

from dataclasses import dataclass, asdict

from dirty_puddle.sim.genome import clamp


@dataclass(frozen=True)
class EnvironmentHealth:
    nutrient_regeneration_capacity: float
    toxin_waste_load: float
    oxygen_light_mineral_availability: float
    ph_stability: float
    salinity_stability: float
    temperature_stability: float
    radiation_stress: float
    biodiversity: float
    biomass_load: float
    extinction_pressure: float
    colony_stability: float
    organism_survival: float
    support_score: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def effective_mutation_rate(
    *,
    base_mutation_rate: float,
    radiation_level: float,
    volatility: float,
    random_catastrophe_frequency: float,
    ph_drift: float,
    salinity_drift: float,
    temperature_drift: float,
    minimum: float,
    maximum: float,
) -> float:
    stress_factor = (
        abs(ph_drift) * 0.020
        + abs(salinity_drift) * 0.018
        + abs(temperature_drift) * 0.020
    )
    value = (
        base_mutation_rate
        + radiation_level * 0.030
        + volatility * 0.015
        + random_catastrophe_frequency * 1.50
        + stress_factor
    )
    return clamp(value, minimum, maximum)


def support_score_from_factors(
    *,
    nutrient_regeneration_capacity: float,
    toxin_waste_load: float,
    oxygen_light_mineral_availability: float,
    ph_stability: float,
    salinity_stability: float,
    temperature_stability: float,
    radiation_stress: float,
    biodiversity: float,
    biomass_load: float,
    extinction_pressure: float,
    colony_stability: float,
    organism_survival: float,
) -> float:
    positive = (
        nutrient_regeneration_capacity * 0.18
        + oxygen_light_mineral_availability * 0.13
        + ph_stability * 0.09
        + salinity_stability * 0.08
        + temperature_stability * 0.08
        + biodiversity * 0.12
        + colony_stability * 0.12
        + organism_survival * 0.10
    )
    negative = (
        toxin_waste_load * 0.13
        + radiation_stress * 0.08
        + max(0.0, biomass_load - 0.72) * 0.18
        + extinction_pressure * 0.10
    )
    return clamp(positive - negative + 0.12, 0.0, 1.0)
