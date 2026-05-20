from __future__ import annotations

from dataclasses import dataclass, field

from aquagenesys.gene_drive.genome import Genome
from aquagenesys.gene_drive.interpreter import Phenotype


@dataclass
class Organism:
    organism_id: int
    lineage_id: int
    genome: Genome
    phenotype: Phenotype
    x: float
    y: float
    vx: float
    vy: float
    energy: float
    generation: int = 0
    age: int = 0
    parent_ids: tuple[int, ...] = field(default_factory=tuple)
    cooldown: int = 0
    last_death_risk: float = 0.0

    @property
    def radius(self) -> float:
        return max(1.2, self.phenotype.size * 0.46)

    @property
    def alive(self) -> bool:
        return self.energy > 0.0

    def payload(self) -> dict[str, object]:
        phenotype = self.phenotype
        return {
            "id": self.organism_id,
            "lineage": self.lineage_id,
            "generation": self.generation,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "vx": round(self.vx, 3),
            "vy": round(self.vy, 3),
            "energy": round(self.energy, 3),
            "age": self.age,
            "radius": round(self.radius, 3),
            "color": phenotype.color,
            "metabolism": phenotype.metabolism_mode,
            "appendages": phenotype.appendages,
            "nubbins": phenotype.nubbins,
            "tail": round(phenotype.tail, 3),
            "cilia": round(phenotype.cilia, 3),
            "irregularity": round(phenotype.irregularity, 3),
            "symmetry": round(phenotype.symmetry, 3),
            "speed": round(phenotype.speed, 3),
            "predation": round(phenotype.predation, 3),
            "mutation_load": round(phenotype.mutation_load, 3),
            "reproduction": phenotype.reproduction_mode,
        }


@dataclass
class GenePacket:
    packet_id: int
    token: str
    x: float
    y: float
    vx: float
    vy: float
    age: int = 0
    parasitic: bool = False

    def payload(self) -> dict[str, object]:
        return {
            "id": self.packet_id,
            "token": self.token,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "age": self.age,
            "parasitic": self.parasitic,
        }
