from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class LifeHistoryGenome(Protocol):
    body_size: float
    max_speed: float
    metabolism: str
    reproduction_rate: float
    risk_tolerance: float
    sociality: float
    dormancy_bias: float
    egg_viability_ticks: int
    parthenogenesis_alleles: int
    parthenogenesis_bias: float
    mutation_load: float


@dataclass(frozen=True)
class LifeHistoryProfile:
    maturity_age_ticks: int
    fertility_end_age_ticks: int
    senescence_start_ticks: int
    expected_lifespan_ticks: int
    reproduction_interval_ticks: int
    base_clutch_size: int
    offspring_investment: float
    brood_strategy: str
    egg_strategy: str
    dormancy_bias: float
    juvenile_investment: float
    parthenogenesis_alleles: int
    parthenogenesis_bias: float
    egg_viability_ticks: int
    dormancy_decay_modifier: float
    hatch_sensitivity: float
    mutation_load: float

    def maturity_state(self, age: int) -> str:
        if age < self.maturity_age_ticks:
            return "juvenile"
        if age >= self.senescence_start_ticks:
            return "senescent"
        return "mature"

    def fertility_state(self, age: int) -> str:
        if age < self.maturity_age_ticks:
            return "immature"
        if age > self.fertility_end_age_ticks:
            return "too_old"
        if age >= self.senescence_start_ticks:
            return "late_fertility"
        return "fertile"

    def payload(self) -> dict[str, Any]:
        return {
            "maturity_age_ticks": self.maturity_age_ticks,
            "fertility_end_age_ticks": self.fertility_end_age_ticks,
            "senescence_start_ticks": self.senescence_start_ticks,
            "expected_lifespan_ticks": self.expected_lifespan_ticks,
            "reproduction_interval_ticks": self.reproduction_interval_ticks,
            "base_clutch_size": self.base_clutch_size,
            "offspring_investment": round(self.offspring_investment, 3),
            "brood_strategy": self.brood_strategy,
            "egg_strategy": self.egg_strategy,
            "dormancy_bias": round(self.dormancy_bias, 3),
            "juvenile_investment": round(self.juvenile_investment, 3),
            "parthenogenesis_alleles": self.parthenogenesis_alleles,
            "parthenogenesis_bias": round(self.parthenogenesis_bias, 3),
            "egg_viability_ticks": self.egg_viability_ticks,
            "dormancy_decay_modifier": round(self.dormancy_decay_modifier, 3),
            "hatch_sensitivity": round(self.hatch_sensitivity, 3),
            "mutation_load": round(self.mutation_load, 3),
        }


def derive_life_history(genome: LifeHistoryGenome) -> LifeHistoryProfile:
    size = clamp(genome.body_size / 1.25)
    reproduction = clamp(genome.reproduction_rate / 1.25)
    speed = clamp(genome.max_speed / 1.25)
    dormancy = clamp(genome.dormancy_bias)
    mutation_load = clamp(genome.mutation_load)

    if genome.metabolism in {"grazer", "filter", "scavenger"}:
        base_maturity = 140
        base_lifespan = 1750
        base_interval = 64
        base_clutch = 6
        brood_strategy = "egg_clutch"
        egg_strategy = "substrate_bank"
        juvenile_investment = 0.36
        investment = 0.46
    elif genome.metabolism == "predator" or size > 0.76:
        base_maturity = 420
        base_lifespan = 2700
        base_interval = 160
        base_clutch = 2
        brood_strategy = "guarded_brood"
        egg_strategy = "guarded_eggs"
        juvenile_investment = 0.72
        investment = 0.30
    else:
        base_maturity = 230
        base_lifespan = 2200
        base_interval = 104
        base_clutch = 4
        brood_strategy = "mixed_brood"
        egg_strategy = "opportunistic_eggs"
        juvenile_investment = 0.54
        investment = 0.38

    maturity = int(base_maturity + size * 170 - reproduction * 115 - speed * 40)
    maturity = max(80, min(820, maturity))
    lifespan = int(base_lifespan + size * 720 - reproduction * 240 + genome.risk_tolerance * 120)
    lifespan = max(maturity + 720, min(3800, lifespan))
    senescence = int(lifespan * (0.72 + min(0.16, genome.sociality * 0.04)))
    fertility_end = int(lifespan * (0.92 + min(0.05, reproduction * 0.04)))
    interval = int(base_interval + size * 48 - reproduction * 54 + genome.sociality * 12)
    interval = max(34, min(260, interval))
    clutch = int(round(base_clutch + reproduction * 3.0 - size * 3.2 + dormancy * 1.4))
    clutch = max(1, min(9, clutch))
    egg_viability = int(genome.egg_viability_ticks + dormancy * 420 - mutation_load * 120)
    egg_viability = max(220, min(1900, egg_viability))
    dormancy_decay = clamp(0.82 - dormancy * 0.48 + mutation_load * 0.14, 0.24, 0.92)
    hatch_sensitivity = clamp(0.62 + reproduction * 0.22 - dormancy * 0.18 - mutation_load * 0.10, 0.36, 0.92)
    parthenogenesis_bias = clamp(genome.parthenogenesis_bias + genome.parthenogenesis_alleles * 0.05 - mutation_load * 0.06)

    return LifeHistoryProfile(
        maturity_age_ticks=maturity,
        fertility_end_age_ticks=max(maturity + 360, fertility_end),
        senescence_start_ticks=max(maturity + 260, senescence),
        expected_lifespan_ticks=lifespan,
        reproduction_interval_ticks=interval,
        base_clutch_size=clutch,
        offspring_investment=clamp(investment + reproduction * 0.10 - size * 0.05, 0.18, 0.62),
        brood_strategy=brood_strategy,
        egg_strategy=egg_strategy,
        dormancy_bias=dormancy,
        juvenile_investment=clamp(juvenile_investment + size * 0.12 - reproduction * 0.08, 0.24, 0.86),
        parthenogenesis_alleles=max(0, min(4, genome.parthenogenesis_alleles)),
        parthenogenesis_bias=parthenogenesis_bias,
        egg_viability_ticks=egg_viability,
        dormancy_decay_modifier=dormancy_decay,
        hatch_sensitivity=hatch_sensitivity,
        mutation_load=mutation_load,
    )
