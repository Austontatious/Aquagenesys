from __future__ import annotations

from dataclasses import dataclass

from dirty_puddle.sim.genome import Genome, clamp
from dirty_puddle.sim.stages import CellStage, stage_for


@dataclass(slots=True)
class Cell:
    id: int
    lineage_id: int
    parent_id: int | None
    genome: Genome
    x: int
    y: int
    energy: float
    age: int = 0
    colony_id: int | None = None
    cooperation_paid: float = 0.0
    public_good_received: float = 0.0
    colony_stress_protection: float = 0.0

    @property
    def pos(self) -> tuple[int, int]:
        return (self.x, self.y)

    def stage(self, max_age: int) -> CellStage:
        return stage_for(self.age, max_age)

    def add_energy(self, amount: float) -> None:
        self.energy = clamp(self.energy + amount, 0.0, self.genome.max_energy)

    def spend_energy(self, amount: float) -> None:
        self.energy -= amount
        if self.energy < 0.0:
            self.energy = 0.0

    def reset_social_state(self) -> None:
        self.colony_id = None
        self.cooperation_paid = 0.0
        self.public_good_received = 0.0
        self.colony_stress_protection = 0.0
