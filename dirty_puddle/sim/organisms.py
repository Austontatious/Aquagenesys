from __future__ import annotations

from dataclasses import asdict, dataclass

from dirty_puddle.sim.genome import clamp


@dataclass(slots=True)
class MulticellularOrganism:
    organism_id: int
    origin_colony_id: int
    origin_lineage_id: int
    age: int
    energy: float
    x: int
    y: int
    body_size: int
    movement_speed: float
    metabolism: float
    stress_tolerance: float
    cooperation_profile: dict[str, float]
    cheater_burden: float
    reproductive_readiness: float
    sensor_profile: dict[str, float]
    feeding_strategy: str
    max_age: int
    offspring_count: int = 0

    @property
    def centroid(self) -> tuple[float, float]:
        return (float(self.x), float(self.y))

    def spend_energy(self, amount: float) -> None:
        self.energy -= amount
        if self.energy < 0.0:
            self.energy = 0.0

    def add_energy(self, amount: float) -> None:
        self.energy = min(self.energy + amount, self.body_size * 8.0 + 30.0)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def ready_to_reproduce(self, threshold: float) -> bool:
        return self.energy >= threshold and self.age >= 20


def organism_from_colony(
    *,
    organism_id: int,
    origin_colony_id: int,
    origin_lineage_id: int,
    x: int,
    y: int,
    body_size: int,
    energy: float,
    traits: dict[str, float],
    max_age: int,
) -> MulticellularOrganism:
    cooperation = traits.get("cooperation", 0.0)
    adhesion = traits.get("adhesion", 0.0)
    selfishness = traits.get("selfishness", 0.0)
    stress_resistance = traits.get("stress_resistance", 0.4)
    return MulticellularOrganism(
        organism_id=organism_id,
        origin_colony_id=origin_colony_id,
        origin_lineage_id=origin_lineage_id,
        age=0,
        energy=energy,
        x=x,
        y=y,
        body_size=max(3, body_size),
        movement_speed=clamp(0.34 + (1.0 - adhesion) * 0.32, 0.06, 0.85),
        metabolism=clamp(0.05 + body_size * 0.0025 + selfishness * 0.035, 0.04, 0.8),
        stress_tolerance=clamp(stress_resistance * 0.65 + cooperation * 0.22 + adhesion * 0.12, 0.0, 1.0),
        cooperation_profile={
            "cooperation": cooperation,
            "nutrient_sharing": traits.get("nutrient_sharing", 0.0),
            "waste_buffering": traits.get("waste_buffering", 0.0),
            "stress_shielding": traits.get("stress_shielding", 0.0),
            "public_good": traits.get("public_good", 0.0),
        },
        cheater_burden=selfishness,
        reproductive_readiness=0.0,
        sensor_profile={
            "nutrient": clamp(0.45 + traits.get("nutrient_affinity", 0.5) * 0.35, 0.0, 1.0),
            "stress": clamp(0.35 + stress_resistance * 0.45, 0.0, 1.0),
            "crowding": clamp(0.25 + (1.0 - selfishness) * 0.35, 0.0, 1.0),
        },
        feeding_strategy="graze_and_scavenge",
        max_age=max_age,
    )
