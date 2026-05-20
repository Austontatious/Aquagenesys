from __future__ import annotations

from dataclasses import dataclass
import math
import random


def clamp(value: float, low: float, high: float) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


@dataclass(frozen=True, slots=True)
class Genome:
    """Heritable cell traits.

    Heat and toxin preferences are niche traits: a cell survives best when the
    local stress field is close to its inherited preference.
    """

    nutrient_affinity: float
    heat_preference: float
    toxin_preference: float
    stress_resistance: float
    mobility: float
    metabolism: float
    reproduction_threshold: float
    max_energy: float
    hue: float
    adhesion: float = 0.28
    nutrient_sharing: float = 0.16
    waste_buffering: float = 0.14
    stress_shielding: float = 0.18
    public_good: float = 0.16
    selfishness: float = 0.18

    @property
    def cooperation(self) -> float:
        return (
            self.nutrient_sharing
            + self.waste_buffering
            + self.stress_shielding
            + self.public_good
        ) * 0.25

    def mutated(
        self,
        rng: random.Random,
        *,
        mutation_rate: float,
        mutation_strength: float,
    ) -> "Genome":
        def maybe_trait(value: float, low: float, high: float) -> float:
            if rng.random() >= mutation_rate:
                return value
            return clamp(value + rng.gauss(0.0, mutation_strength), low, high)

        return Genome(
            nutrient_affinity=maybe_trait(self.nutrient_affinity, 0.05, 1.25),
            heat_preference=maybe_trait(self.heat_preference, 0.0, 1.0),
            toxin_preference=maybe_trait(self.toxin_preference, 0.0, 1.0),
            stress_resistance=maybe_trait(self.stress_resistance, 0.0, 1.0),
            mobility=maybe_trait(self.mobility, 0.0, 1.0),
            metabolism=maybe_trait(self.metabolism, 0.03, 0.45),
            reproduction_threshold=maybe_trait(self.reproduction_threshold, 7.0, 18.0),
            max_energy=maybe_trait(self.max_energy, 10.0, 28.0),
            hue=maybe_trait(self.hue, 0.0, 1.0),
            adhesion=maybe_trait(self.adhesion, 0.0, 1.0),
            nutrient_sharing=maybe_trait(self.nutrient_sharing, 0.0, 1.0),
            waste_buffering=maybe_trait(self.waste_buffering, 0.0, 1.0),
            stress_shielding=maybe_trait(self.stress_shielding, 0.0, 1.0),
            public_good=maybe_trait(self.public_good, 0.0, 1.0),
            selfishness=maybe_trait(self.selfishness, 0.0, 1.0),
        )

    def distance(self, other: "Genome") -> float:
        values = (
            abs(self.nutrient_affinity - other.nutrient_affinity),
            abs(self.heat_preference - other.heat_preference),
            abs(self.toxin_preference - other.toxin_preference),
            abs(self.stress_resistance - other.stress_resistance),
            abs(self.mobility - other.mobility),
            abs(self.metabolism - other.metabolism),
            abs(self.reproduction_threshold - other.reproduction_threshold) / 18.0,
            abs(self.max_energy - other.max_energy) / 28.0,
            abs(self.hue - other.hue),
            abs(self.adhesion - other.adhesion),
            abs(self.nutrient_sharing - other.nutrient_sharing),
            abs(self.waste_buffering - other.waste_buffering),
            abs(self.stress_shielding - other.stress_shielding),
            abs(self.public_good - other.public_good),
            abs(self.selfishness - other.selfishness),
        )
        return math.fsum(values) / len(values)

    def color(self) -> tuple[int, int, int]:
        return hsl_to_rgb(self.hue, 0.72, 0.58)

    def signature(self) -> dict[str, float]:
        return {
            "nutrient_affinity": round(self.nutrient_affinity, 4),
            "heat_preference": round(self.heat_preference, 4),
            "toxin_preference": round(self.toxin_preference, 4),
            "stress_resistance": round(self.stress_resistance, 4),
            "mobility": round(self.mobility, 4),
            "metabolism": round(self.metabolism, 4),
            "reproduction_threshold": round(self.reproduction_threshold, 4),
            "max_energy": round(self.max_energy, 4),
            "hue": round(self.hue, 4),
            "adhesion": round(self.adhesion, 4),
            "nutrient_sharing": round(self.nutrient_sharing, 4),
            "waste_buffering": round(self.waste_buffering, 4),
            "stress_shielding": round(self.stress_shielding, 4),
            "public_good": round(self.public_good, 4),
            "selfishness": round(self.selfishness, 4),
        }


def hsl_to_rgb(h: float, s: float, lightness: float) -> tuple[int, int, int]:
    h = h % 1.0

    def channel(n: float) -> float:
        k = (n + h * 12.0) % 12.0
        a = s * min(lightness, 1.0 - lightness)
        return lightness - a * max(-1.0, min(k - 3.0, 9.0 - k, 1.0))

    return (
        int(clamp(channel(0.0), 0.0, 1.0) * 255),
        int(clamp(channel(8.0), 0.0, 1.0) * 255),
        int(clamp(channel(4.0), 0.0, 1.0) * 255),
    )


def founder_genomes() -> tuple[Genome, Genome, Genome]:
    return (
        Genome(
            nutrient_affinity=0.86,
            heat_preference=0.18,
            toxin_preference=0.20,
            stress_resistance=0.38,
            mobility=0.35,
            metabolism=0.13,
            reproduction_threshold=10.5,
            max_energy=17.0,
            hue=0.33,
            adhesion=0.72,
            nutrient_sharing=0.34,
            waste_buffering=0.26,
            stress_shielding=0.30,
            public_good=0.32,
            selfishness=0.12,
        ),
        Genome(
            nutrient_affinity=0.74,
            heat_preference=0.82,
            toxin_preference=0.24,
            stress_resistance=0.66,
            mobility=0.42,
            metabolism=0.16,
            reproduction_threshold=11.5,
            max_energy=18.0,
            hue=0.04,
            adhesion=0.48,
            nutrient_sharing=0.20,
            waste_buffering=0.16,
            stress_shielding=0.22,
            public_good=0.18,
            selfishness=0.42,
        ),
        Genome(
            nutrient_affinity=0.78,
            heat_preference=0.34,
            toxin_preference=0.84,
            stress_resistance=0.70,
            mobility=0.39,
            metabolism=0.17,
            reproduction_threshold=11.8,
            max_energy=18.5,
            hue=0.58,
            adhesion=0.60,
            nutrient_sharing=0.18,
            waste_buffering=0.42,
            stress_shielding=0.46,
            public_good=0.24,
            selfishness=0.24,
        ),
    )


def average_genome_traits(cells: list[object]) -> dict[str, float]:
    if not cells:
        return {}
    genomes = [cell.genome for cell in cells]
    total = float(len(genomes))
    return {
        "nutrient_affinity": math.fsum(genome.nutrient_affinity for genome in genomes) / total,
        "stress_resistance": math.fsum(genome.stress_resistance for genome in genomes) / total,
        "adhesion": math.fsum(genome.adhesion for genome in genomes) / total,
        "cooperation": math.fsum(genome.cooperation for genome in genomes) / total,
        "nutrient_sharing": math.fsum(genome.nutrient_sharing for genome in genomes) / total,
        "waste_buffering": math.fsum(genome.waste_buffering for genome in genomes) / total,
        "stress_shielding": math.fsum(genome.stress_shielding for genome in genomes) / total,
        "public_good": math.fsum(genome.public_good for genome in genomes) / total,
        "selfishness": math.fsum(genome.selfishness for genome in genomes) / total,
    }
