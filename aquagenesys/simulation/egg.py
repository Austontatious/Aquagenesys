from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aquagenesys.agents.fish import FishGenome


@dataclass
class EggEntity:
    egg_id: int
    parent_ids: tuple[int, ...]
    lineage_id: int
    species_id: str
    genome: FishGenome
    generation: int
    created_tick: int
    age_ticks: int
    gestation_ticks: int
    viability: float
    energy_investment: float
    x: float
    y: float
    dormant: bool
    dormancy_strategy: str
    hatch_sensitivity: float
    decay_rate: float
    parthenogenetic: bool = False
    state: str = "gestating"
    death_cause: str = ""

    @property
    def viable(self) -> bool:
        return self.state in {"gestating", "dormant"} and self.viability > 0.0

    def mark_dormant(self) -> None:
        if self.state == "gestating":
            self.dormant = True
            self.state = "dormant"

    def mark_dead(self, cause: str) -> None:
        self.state = "dead"
        self.death_cause = cause
        self.viability = 0.0

    def mark_hatched(self) -> None:
        self.state = "hatched"

    def payload(self, *, compact: bool = False) -> dict[str, Any]:
        payload = {
            "egg_id": self.egg_id,
            "lineage_id": self.lineage_id,
            "species_id": self.species_id,
            "parent_ids": list(self.parent_ids),
            "generation": self.generation,
            "age_ticks": self.age_ticks,
            "gestation_ticks": self.gestation_ticks,
            "viability": round(self.viability, 3),
            "energy_investment": round(self.energy_investment, 3),
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "dormant": self.dormant,
            "dormancy_strategy": self.dormancy_strategy,
            "state": self.state,
            "parthenogenetic": self.parthenogenetic,
            "death_cause": self.death_cause,
        }
        if compact:
            return payload
        payload["genome"] = self.genome.payload()
        payload["phenotype"] = self.genome.phenotype_payload(compact=True)
        payload["hatch_sensitivity"] = round(self.hatch_sensitivity, 3)
        payload["decay_rate"] = round(self.decay_rate, 5)
        payload["created_tick"] = self.created_tick
        return payload
