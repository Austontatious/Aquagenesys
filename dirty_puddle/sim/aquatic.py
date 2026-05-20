from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random

from dirty_puddle.sim.genome import clamp
from dirty_puddle.sim.organisms import MulticellularOrganism


@dataclass(slots=True)
class AquaticOrganism:
    aquatic_id: int
    origin_organism_id: int
    origin_lineage_id: int
    age: int
    energy: float
    x: float
    y: float
    vx: float
    vy: float
    body_size: float
    movement_speed: float
    turn_rate: float
    metabolism: float
    stress_tolerance: float
    feeding_strategy: str
    aggression: float
    defense: float
    reproduction_threshold: float
    sensory_radius: int
    preferred_environment_profile: dict[str, float]
    color_marker: tuple[int, int, int]
    max_age: int
    offspring_count: int = 0

    @property
    def position(self) -> tuple[float, float]:
        return (self.x, self.y)

    @property
    def velocity(self) -> tuple[float, float]:
        return (self.vx, self.vy)

    def spend_energy(self, amount: float) -> None:
        self.energy -= amount
        if self.energy < 0.0:
            self.energy = 0.0

    def add_energy(self, amount: float) -> None:
        self.energy = min(self.energy + amount, self.body_size * 10.0 + 60.0)

    def ready_to_reproduce(self, minimum_age: int) -> bool:
        return self.age >= minimum_age and self.energy >= self.reproduction_threshold

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["position"] = [self.x, self.y]
        data["velocity"] = [self.vx, self.vy]
        return data


def aquatic_from_organism(
    *,
    aquatic_id: int,
    organism: MulticellularOrganism,
    reproduction_threshold: float,
    max_age: int,
    rng: random.Random,
    color_marker: tuple[int, int, int],
) -> AquaticOrganism:
    nutrient_sensor = organism.sensor_profile.get("nutrient", 0.5)
    stress_sensor = organism.sensor_profile.get("stress", 0.5)
    crowding_sensor = organism.sensor_profile.get("crowding", 0.5)
    cooperation = organism.cooperation_profile.get("cooperation", 0.0)
    cheater_burden = organism.cheater_burden
    angle = rng.random() * math.tau
    speed = clamp(organism.movement_speed + nutrient_sensor * 0.22, 0.08, 1.35)
    return AquaticOrganism(
        aquatic_id=aquatic_id,
        origin_organism_id=organism.organism_id,
        origin_lineage_id=organism.origin_lineage_id,
        age=0,
        energy=max(12.0, organism.energy * 0.55),
        x=float(organism.x),
        y=float(organism.y),
        vx=math.cos(angle) * speed * 0.35,
        vy=math.sin(angle) * speed * 0.35,
        body_size=clamp(float(organism.body_size) * 1.25, 3.0, 80.0),
        movement_speed=speed,
        turn_rate=clamp(0.18 + stress_sensor * 0.42, 0.05, 0.85),
        metabolism=clamp(organism.metabolism * 1.35 + speed * 0.045, 0.04, 2.0),
        stress_tolerance=clamp(organism.stress_tolerance + cooperation * 0.18, 0.0, 1.4),
        feeding_strategy="graze_hunt" if cheater_burden > 0.36 else "graze_filter",
        aggression=clamp(cheater_burden * 0.62 + (1.0 - cooperation) * 0.18, 0.0, 1.0),
        defense=clamp(organism.stress_tolerance * 0.45 + cooperation * 0.25 + crowding_sensor * 0.16, 0.0, 1.0),
        reproduction_threshold=reproduction_threshold,
        sensory_radius=max(2, int(round(2 + nutrient_sensor * 5 + stress_sensor * 2))),
        preferred_environment_profile={
            "heat": 0.48,
            "toxin": clamp(0.22 + (1.0 - organism.stress_tolerance) * 0.22, 0.0, 1.0),
            "nutrient": clamp(0.35 + nutrient_sensor * 0.45, 0.0, 1.0),
        },
        color_marker=color_marker,
        max_age=max_age,
    )


def child_aquatic(
    *,
    aquatic_id: int,
    parent: AquaticOrganism,
    x: float,
    y: float,
    rng: random.Random,
) -> AquaticOrganism:
    def jitter(value: float, spread: float, low: float, high: float) -> float:
        return clamp(value + rng.gauss(0.0, spread), low, high)

    angle = math.atan2(parent.vy, parent.vx) + rng.gauss(0.0, 0.55)
    speed = jitter(parent.movement_speed, 0.035, 0.05, 1.5)
    return AquaticOrganism(
        aquatic_id=aquatic_id,
        origin_organism_id=parent.origin_organism_id,
        origin_lineage_id=parent.origin_lineage_id,
        age=0,
        energy=max(8.0, parent.energy * 0.32),
        x=x,
        y=y,
        vx=math.cos(angle) * speed * 0.35,
        vy=math.sin(angle) * speed * 0.35,
        body_size=jitter(parent.body_size * 0.72, 0.4, 2.0, 100.0),
        movement_speed=speed,
        turn_rate=jitter(parent.turn_rate, 0.025, 0.03, 0.95),
        metabolism=jitter(parent.metabolism, 0.025, 0.02, 2.4),
        stress_tolerance=jitter(parent.stress_tolerance, 0.035, 0.0, 1.5),
        feeding_strategy=parent.feeding_strategy,
        aggression=jitter(parent.aggression, 0.035, 0.0, 1.0),
        defense=jitter(parent.defense, 0.035, 0.0, 1.0),
        reproduction_threshold=jitter(parent.reproduction_threshold, 1.2, 8.0, 500.0),
        sensory_radius=max(1, int(round(jitter(float(parent.sensory_radius), 0.5, 1.0, 12.0)))),
        preferred_environment_profile=dict(parent.preferred_environment_profile),
        color_marker=parent.color_marker,
        max_age=parent.max_age,
    )
