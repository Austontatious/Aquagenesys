from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from math import hypot
from random import Random
from typing import Any


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def unit(dx: float, dy: float) -> tuple[float, float]:
    magnitude = hypot(dx, dy)
    if magnitude <= 1e-9:
        return (0.0, 0.0)
    return (dx / magnitude, dy / magnitude)


def mutate_hex_color(value: str, rng: Random, *, spread: int = 9) -> str:
    raw = value.removeprefix("#")
    if len(raw) != 6:
        return value
    try:
        channels = [int(raw[index : index + 2], 16) for index in (0, 2, 4)]
    except ValueError:
        return value
    shifted = [max(22, min(238, channel + int(rng.gauss(0, spread)))) for channel in channels]
    return "#" + "".join(f"{channel:02x}" for channel in shifted)


@dataclass(frozen=True)
class FishGenome:
    archetype: str
    species_id: str
    lineage_id: int
    body_size: float
    max_speed: float
    turning: float
    metabolism: str
    oxygen_need: float
    ph_preference: float
    temperature_preference: float
    turbidity_tolerance: float
    toxin_tolerance: float
    risk_tolerance: float
    sociality: float
    aggression: float
    curiosity: float
    reproduction_rate: float
    sensory_range: float
    deliberation_chance: float
    memory_span: int
    color: str
    accent_color: str
    body_shape: str
    tail_shape: str
    fin_shape: str
    pattern: str
    body_depth: float
    tail_length: float
    fin_span: float
    pattern_density: float
    pattern_contrast: float
    iridescence: float
    camouflage: float
    eye_scale: float
    barbel_length: float

    @classmethod
    def founder(cls, rng: Random, *, lineage_id: int, archetype: str) -> "FishGenome":
        palettes = {
            "silt_grazer": ("#b9d36b", "#3c4f2f"),
            "glass_filter": ("#8fd6db", "#174a52"),
            "mud_stalker": ("#d28b64", "#3b1716"),
            "reed_sprinter": ("#d7c36f", "#293d37"),
        }
        color, accent = palettes[archetype]
        base = {
            "silt_grazer": {
                "body_size": 0.72,
                "max_speed": 0.56,
                "turning": 0.62,
                "metabolism": "grazer",
                "oxygen_need": 0.46,
                "risk_tolerance": 0.38,
                "sociality": 0.68,
                "aggression": 0.12,
                "curiosity": 0.42,
                "reproduction_rate": 0.58,
                "sensory_range": 8.0,
                "deliberation_chance": 0.10,
                "body_shape": "leaf",
                "tail_shape": "rounded",
                "fin_shape": "broad",
                "pattern": "speckled",
                "body_depth": 0.72,
                "tail_length": 0.55,
                "fin_span": 0.78,
                "pattern_density": 0.74,
                "pattern_contrast": 0.42,
                "iridescence": 0.18,
                "camouflage": 0.76,
                "eye_scale": 0.72,
                "barbel_length": 0.65,
            },
            "glass_filter": {
                "body_size": 0.56,
                "max_speed": 0.48,
                "turning": 0.74,
                "metabolism": "filter",
                "oxygen_need": 0.52,
                "risk_tolerance": 0.34,
                "sociality": 0.82,
                "aggression": 0.04,
                "curiosity": 0.36,
                "reproduction_rate": 0.66,
                "sensory_range": 9.5,
                "deliberation_chance": 0.08,
                "body_shape": "ribbon",
                "tail_shape": "forked",
                "fin_shape": "glass",
                "pattern": "countershade",
                "body_depth": 0.45,
                "tail_length": 0.64,
                "fin_span": 0.52,
                "pattern_density": 0.25,
                "pattern_contrast": 0.28,
                "iridescence": 0.72,
                "camouflage": 0.58,
                "eye_scale": 0.62,
                "barbel_length": 0.05,
            },
            "mud_stalker": {
                "body_size": 0.95,
                "max_speed": 0.68,
                "turning": 0.46,
                "metabolism": "predator",
                "oxygen_need": 0.58,
                "risk_tolerance": 0.62,
                "sociality": 0.24,
                "aggression": 0.76,
                "curiosity": 0.54,
                "reproduction_rate": 0.34,
                "sensory_range": 11.0,
                "deliberation_chance": 0.18,
                "body_shape": "heavy",
                "tail_shape": "spade",
                "fin_shape": "spiked",
                "pattern": "saddle",
                "body_depth": 0.82,
                "tail_length": 0.48,
                "fin_span": 0.60,
                "pattern_density": 0.46,
                "pattern_contrast": 0.68,
                "iridescence": 0.08,
                "camouflage": 0.64,
                "eye_scale": 0.88,
                "barbel_length": 0.25,
            },
            "reed_sprinter": {
                "body_size": 0.64,
                "max_speed": 0.82,
                "turning": 0.66,
                "metabolism": "omnivore",
                "oxygen_need": 0.50,
                "risk_tolerance": 0.50,
                "sociality": 0.48,
                "aggression": 0.34,
                "curiosity": 0.72,
                "reproduction_rate": 0.46,
                "sensory_range": 10.0,
                "deliberation_chance": 0.14,
                "body_shape": "torpedo",
                "tail_shape": "lunate",
                "fin_shape": "swept",
                "pattern": "banded",
                "body_depth": 0.54,
                "tail_length": 0.82,
                "fin_span": 0.46,
                "pattern_density": 0.52,
                "pattern_contrast": 0.62,
                "iridescence": 0.34,
                "camouflage": 0.42,
                "eye_scale": 0.70,
                "barbel_length": 0.10,
            },
        }[archetype]
        jitter = lambda value, spread=0.08: clamp(value + rng.uniform(-spread, spread), 0.02, 1.25)
        species_id = f"{archetype}-{lineage_id:03d}"
        return cls(
            archetype=archetype,
            species_id=species_id,
            lineage_id=lineage_id,
            body_size=jitter(base["body_size"], 0.10),
            max_speed=jitter(base["max_speed"], 0.10),
            turning=jitter(base["turning"], 0.10),
            metabolism=str(base["metabolism"]),
            oxygen_need=jitter(base["oxygen_need"], 0.06),
            ph_preference=clamp(rng.uniform(0.46, 0.57)),
            temperature_preference=clamp(rng.uniform(0.42, 0.58)),
            turbidity_tolerance=clamp(rng.uniform(0.28, 0.72)),
            toxin_tolerance=clamp(rng.uniform(0.22, 0.68)),
            risk_tolerance=jitter(base["risk_tolerance"], 0.10),
            sociality=jitter(base["sociality"], 0.12),
            aggression=jitter(base["aggression"], 0.10),
            curiosity=jitter(base["curiosity"], 0.12),
            reproduction_rate=jitter(base["reproduction_rate"], 0.10),
            sensory_range=max(4.0, float(base["sensory_range"]) + rng.uniform(-1.8, 1.8)),
            deliberation_chance=jitter(base["deliberation_chance"], 0.04),
            memory_span=rng.randint(10, 18),
            color=color,
            accent_color=accent,
            body_shape=str(base["body_shape"]),
            tail_shape=str(base["tail_shape"]),
            fin_shape=str(base["fin_shape"]),
            pattern=str(base["pattern"]),
            body_depth=clamp(float(base["body_depth"]), 0.02, 1.25),
            tail_length=clamp(float(base["tail_length"]), 0.02, 1.25),
            fin_span=clamp(float(base["fin_span"]), 0.02, 1.25),
            pattern_density=clamp(float(base["pattern_density"]), 0.02, 1.25),
            pattern_contrast=clamp(float(base["pattern_contrast"]), 0.02, 1.25),
            iridescence=clamp(float(base["iridescence"]), 0.02, 1.25),
            camouflage=clamp(float(base["camouflage"]), 0.02, 1.25),
            eye_scale=clamp(float(base["eye_scale"]), 0.02, 1.25),
            barbel_length=clamp(float(base["barbel_length"]), 0.0, 1.25),
        )

    def mutated(self, rng: Random, *, lineage_id: int | None = None) -> "FishGenome":
        def m(value: float, spread: float = 0.055) -> float:
            return clamp(value + rng.gauss(0.0, spread), 0.02, 1.25)

        metabolism = self.metabolism
        if rng.random() < 0.025:
            metabolism = rng.choice(["grazer", "filter", "omnivore", "predator", "scavenger"])
        body_shape = self.body_shape
        tail_shape = self.tail_shape
        fin_shape = self.fin_shape
        pattern = self.pattern
        if rng.random() < 0.020:
            body_shape = rng.choice(["leaf", "ribbon", "heavy", "torpedo", "deep"])
        if rng.random() < 0.020:
            tail_shape = rng.choice(["rounded", "forked", "spade", "lunate", "fan"])
        if rng.random() < 0.020:
            fin_shape = rng.choice(["broad", "glass", "spiked", "swept", "short"])
        if rng.random() < 0.030:
            pattern = rng.choice(["speckled", "countershade", "saddle", "banded", "striped"])
        next_lineage = self.lineage_id if lineage_id is None else lineage_id
        return FishGenome(
            archetype=self.archetype if lineage_id is None else metabolism,
            species_id=self.species_id if lineage_id is None else f"{metabolism}-{next_lineage:03d}",
            lineage_id=next_lineage,
            body_size=m(self.body_size),
            max_speed=m(self.max_speed),
            turning=m(self.turning),
            metabolism=metabolism,
            oxygen_need=m(self.oxygen_need),
            ph_preference=clamp(self.ph_preference + rng.gauss(0.0, 0.025)),
            temperature_preference=clamp(self.temperature_preference + rng.gauss(0.0, 0.025)),
            turbidity_tolerance=m(self.turbidity_tolerance),
            toxin_tolerance=m(self.toxin_tolerance),
            risk_tolerance=m(self.risk_tolerance),
            sociality=m(self.sociality),
            aggression=m(self.aggression),
            curiosity=m(self.curiosity),
            reproduction_rate=m(self.reproduction_rate),
            sensory_range=max(3.0, self.sensory_range + rng.gauss(0.0, 0.8)),
            deliberation_chance=clamp(self.deliberation_chance + rng.gauss(0.0, 0.025), 0.02, 0.36),
            memory_span=max(6, min(24, self.memory_span + rng.choice([-1, 0, 1]))),
            color=mutate_hex_color(self.color, rng, spread=7),
            accent_color=mutate_hex_color(self.accent_color, rng, spread=6),
            body_shape=body_shape,
            tail_shape=tail_shape,
            fin_shape=fin_shape,
            pattern=pattern,
            body_depth=m(self.body_depth, 0.045),
            tail_length=m(self.tail_length, 0.045),
            fin_span=m(self.fin_span, 0.045),
            pattern_density=m(self.pattern_density, 0.055),
            pattern_contrast=m(self.pattern_contrast, 0.055),
            iridescence=m(self.iridescence, 0.040),
            camouflage=m(self.camouflage, 0.045),
            eye_scale=m(self.eye_scale, 0.040),
            barbel_length=m(self.barbel_length, 0.055),
        )

    def phenotype_payload(self, *, compact: bool = False) -> dict[str, Any]:
        body_length = 1.22 + self.body_size * 0.52 + self.max_speed * 0.16
        body_depth = 0.42 + self.body_depth * 0.54
        tail_length = 0.44 + self.tail_length * 0.62
        fin_span = 0.26 + self.fin_span * 0.72
        stripe_count = max(2, min(9, int(round(2 + self.pattern_density * 5 + self.pattern_contrast * 2))))
        spot_count = max(3, min(16, int(round(4 + self.pattern_density * 9 + self.camouflage * 2))))
        payload = {
            "shape": self.body_shape,
            "pattern": self.pattern,
            "tail": self.tail_shape,
            "fins": self.fin_shape,
            "body_length": round(body_length, 3),
            "body_depth": round(body_depth, 3),
            "tail_length": round(tail_length, 3),
            "fin_span": round(fin_span, 3),
            "stripe_count": stripe_count,
            "spot_count": spot_count,
            "pattern_density": round(self.pattern_density, 3),
            "pattern_contrast": round(self.pattern_contrast, 3),
            "iridescence": round(self.iridescence, 3),
            "camouflage": round(self.camouflage, 3),
            "eye_scale": round(self.eye_scale, 3),
            "barbel_length": round(self.barbel_length, 3),
            "primary_color": self.color,
            "accent_color": self.accent_color,
        }
        if compact:
            return payload
        payload["mechanics"] = {
            "thrust": round(0.88 + self.tail_length * 0.20 + self.max_speed * 0.08, 3),
            "maneuver": round(0.84 + self.fin_span * 0.18 + self.turning * 0.08, 3),
            "drag": round(0.82 + self.body_depth * 0.16 + self.body_size * 0.08, 3),
            "visibility": round(0.72 + self.iridescence * 0.18 + self.pattern_contrast * 0.12 - self.camouflage * 0.20, 3),
        }
        return payload

    def payload(self) -> dict[str, Any]:
        return {
            "archetype": self.archetype,
            "species_id": self.species_id,
            "lineage_id": self.lineage_id,
            "body_size": round(self.body_size, 3),
            "max_speed": round(self.max_speed, 3),
            "turning": round(self.turning, 3),
            "metabolism": self.metabolism,
            "oxygen_need": round(self.oxygen_need, 3),
            "ph_preference": round(self.ph_preference, 3),
            "temperature_preference": round(self.temperature_preference, 3),
            "turbidity_tolerance": round(self.turbidity_tolerance, 3),
            "toxin_tolerance": round(self.toxin_tolerance, 3),
            "risk_tolerance": round(self.risk_tolerance, 3),
            "sociality": round(self.sociality, 3),
            "aggression": round(self.aggression, 3),
            "curiosity": round(self.curiosity, 3),
            "reproduction_rate": round(self.reproduction_rate, 3),
            "sensory_range": round(self.sensory_range, 3),
            "deliberation_chance": round(self.deliberation_chance, 3),
            "memory_span": self.memory_span,
            "color": self.color,
            "accent_color": self.accent_color,
            "body_shape": self.body_shape,
            "tail_shape": self.tail_shape,
            "fin_shape": self.fin_shape,
            "pattern": self.pattern,
            "body_depth": round(self.body_depth, 3),
            "tail_length": round(self.tail_length, 3),
            "fin_span": round(self.fin_span, 3),
            "pattern_density": round(self.pattern_density, 3),
            "pattern_contrast": round(self.pattern_contrast, 3),
            "iridescence": round(self.iridescence, 3),
            "camouflage": round(self.camouflage, 3),
            "eye_scale": round(self.eye_scale, 3),
            "barbel_length": round(self.barbel_length, 3),
            "phenotype": self.phenotype_payload(),
        }


@dataclass
class Action:
    kind: str
    dx: float
    dy: float
    intensity: float
    source: str
    reason: str
    confidence: float = 0.5

    def normalized(self) -> "Action":
        dx, dy = unit(self.dx, self.dy)
        return Action(
            kind=self.kind,
            dx=dx,
            dy=dy,
            intensity=clamp(self.intensity),
            source=self.source,
            reason=self.reason[:180],
            confidence=clamp(self.confidence),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "dx": round(self.dx, 3),
            "dy": round(self.dy, 3),
            "intensity": round(self.intensity, 3),
            "source": self.source,
            "reason": self.reason,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class Perception:
    sample: dict[str, float]
    gradients: dict[str, tuple[float, float]]
    nearest_food: tuple[float, float, float]
    nearest_shelter: tuple[float, float, float]
    nearest_mate: tuple[float, float, float]
    nearest_prey: tuple[float, float, float]
    nearest_threat: tuple[float, float, float]
    neighbor_count: int
    crowding: float
    stress: float
    resource_score: float
    reproduction_score: float
    edge_vector: tuple[float, float]

    def vector_for(self, target: str) -> tuple[float, float]:
        if target == "food":
            return (self.nearest_food[0], self.nearest_food[1])
        if target == "shelter":
            return (self.nearest_shelter[0], self.nearest_shelter[1])
        if target == "mate":
            return (self.nearest_mate[0], self.nearest_mate[1])
        if target == "prey":
            return (self.nearest_prey[0], self.nearest_prey[1])
        if target == "threat":
            return (-self.nearest_threat[0], -self.nearest_threat[1])
        return (0.0, 0.0)

    def payload(self) -> dict[str, Any]:
        def rounded_pair(pair: tuple[float, float]) -> list[float]:
            return [round(pair[0], 3), round(pair[1], 3)]

        return {
            "sample": {key: round(value, 3) for key, value in self.sample.items()},
            "gradients": {key: rounded_pair(value) for key, value in self.gradients.items()},
            "nearest_food": [round(value, 3) for value in self.nearest_food],
            "nearest_shelter": [round(value, 3) for value in self.nearest_shelter],
            "nearest_mate": [round(value, 3) for value in self.nearest_mate],
            "nearest_prey": [round(value, 3) for value in self.nearest_prey],
            "nearest_threat": [round(value, 3) for value in self.nearest_threat],
            "neighbor_count": self.neighbor_count,
            "crowding": round(self.crowding, 3),
            "stress": round(self.stress, 3),
            "resource_score": round(self.resource_score, 3),
            "reproduction_score": round(self.reproduction_score, 3),
            "edge_vector": rounded_pair(self.edge_vector),
        }


@dataclass
class FishMemory:
    events: list[dict[str, Any]] = field(default_factory=list)

    def record(self, tick: int, action: Action, *, outcome: str, delta_energy: float, delta_health: float) -> None:
        self.events.append(
            {
                "tick": tick,
                "action": action.kind,
                "source": action.source,
                "reason": action.reason,
                "outcome": outcome,
                "delta_energy": round(delta_energy, 3),
                "delta_health": round(delta_health, 3),
            }
        )

    def trim(self, span: int) -> None:
        if len(self.events) > span:
            del self.events[: len(self.events) - span]

    def summary(self) -> dict[str, Any]:
        recent = self.events[-8:]
        outcomes = Counter(event["outcome"] for event in recent)
        actions = Counter(event["action"] for event in recent)
        return {
            "recent_count": len(recent),
            "common_actions": actions.most_common(4),
            "common_outcomes": outcomes.most_common(4),
            "last_events": recent[-4:],
        }

    def payload(self) -> dict[str, Any]:
        return {"summary": self.summary(), "recent": self.events[-6:]}


@dataclass
class FishAgent:
    fish_id: int
    species_id: str
    lineage_id: int
    genome: FishGenome
    x: float
    y: float
    vx: float
    vy: float
    energy: float
    hunger: float
    fear: float
    stress: float
    health: float
    reproductive_drive: float
    age: int = 0
    generation: int = 0
    parent_ids: tuple[int, ...] = field(default_factory=tuple)
    model_budget: int = 0
    deliberation_cooldown: int = 0
    memory: FishMemory = field(default_factory=FishMemory)
    recent_outcomes: list[str] = field(default_factory=list)
    last_perception: Perception | None = None
    last_decision: Action = field(default_factory=lambda: Action("drift", 0.0, 0.0, 0.2, "init", "initial drift"))
    model_intent: Action | None = None
    model_intent_ttl: int = 0
    last_model_decision: Action | None = None
    model_pending: bool = False
    alive: bool = True

    @property
    def radius(self) -> float:
        return max(1.6, 1.45 + self.genome.body_size * 2.0 + self.genome.body_depth * 0.52)

    @property
    def body_state(self) -> str:
        if self.health < 0.28:
            return "failing"
        if self.hunger > 0.78:
            return "starving"
        if self.fear > 0.72:
            return "panicked"
        if self.reproductive_drive > 0.78:
            return "breeding"
        return "viable"

    def update_internal_state(self, perception: Perception) -> None:
        self.age += 1
        if self.deliberation_cooldown > 0:
            self.deliberation_cooldown -= 1
        if self.model_intent_ttl > 0:
            self.model_intent_ttl -= 1
            if self.model_intent_ttl <= 0:
                self.model_intent = None
        self.hunger = clamp(self.hunger + 0.026 + self.genome.body_size * 0.006 - self.energy * 0.0009)
        self.stress = clamp(self.stress * 0.72 + perception.stress * 0.28)
        threat_signal = 1.0 - clamp(perception.nearest_threat[2] / max(1.0, self.genome.sensory_range))
        self.fear = clamp(self.fear * 0.80 + max(0.0, threat_signal - 0.25) * 0.28 + self.stress * 0.12)
        if perception.resource_score > 0.48 and self.health > 0.58:
            self.reproductive_drive = clamp(
                self.reproductive_drive
                + 0.006 * self.genome.reproduction_rate
                + max(0.0, self.energy - 52.0) * 0.0007
            )
        else:
            self.reproductive_drive = clamp(self.reproductive_drive - 0.012)
        self.health = clamp(self.health - max(0.0, self.stress - 0.48) * 0.018 - max(0.0, self.hunger - 0.80) * 0.020)
        self.last_perception = perception

    def reflex_action(self, perception: Perception) -> Action | None:
        if self.health < 0.18:
            dx, dy = perception.vector_for("shelter")
            return Action("shelter", dx, dy, 0.72, "reflex", "critical health seeks shelter", 0.88).normalized()
        if perception.stress > 0.72 and self.genome.risk_tolerance < 0.72:
            stress_dx, stress_dy = perception.gradients["stress"]
            edge_dx, edge_dy = perception.edge_vector
            return Action(
                "escape",
                -stress_dx + edge_dx,
                -stress_dy + edge_dy,
                0.84,
                "reflex",
                "local chemistry is hostile",
                0.82,
            ).normalized()
        if self.fear > 0.76:
            dx, dy = perception.vector_for("threat")
            return Action("flee", dx, dy, 0.92, "reflex", "nearby threat dominates", 0.80).normalized()
        if self.hunger > 0.90 and perception.nearest_food[2] < self.genome.sensory_range * 1.6:
            dx, dy = perception.vector_for("food")
            return Action("eat", dx, dy, 0.88, "reflex", "hunger near starvation", 0.78).normalized()
        return None

    def heuristic_action(self, perception: Perception, rng: Random) -> Action:
        if (
            self.genome.metabolism == "predator"
            and self.hunger > 0.48
            and perception.nearest_prey[2] < self.genome.sensory_range
        ):
            dx, dy = perception.vector_for("prey")
            return Action("hunt", dx, dy, 0.74, "habit", "predator tracks reachable prey", 0.68).normalized()
        if self.reproductive_drive > 0.70 and perception.reproduction_score > 0.50 and perception.nearest_mate[2] < 18.0:
            dx, dy = perception.vector_for("mate")
            return Action("court", dx, dy, 0.58, "habit", "reproductive drive and viable water", 0.64).normalized()
        if self.hunger > 0.44 or perception.resource_score > 0.62:
            dx, dy = perception.vector_for("food")
            return Action("forage", dx, dy, 0.60 + self.hunger * 0.24, "habit", "resource-seeking policy", 0.62).normalized()
        if self.stress > 0.44 or self.fear > 0.44:
            dx, dy = perception.vector_for("shelter")
            return Action("shelter", dx, dy, 0.52, "habit", "stress favors shelter", 0.58).normalized()
        if perception.neighbor_count > 0 and self.genome.sociality > 0.52:
            dx, dy = perception.vector_for("mate")
            return Action("school", dx, dy, 0.36, "habit", "social genome schools loosely", 0.52).normalized()
        angle_x = rng.uniform(-1.0, 1.0) + perception.gradients["current"][0] * 0.8
        angle_y = rng.uniform(-1.0, 1.0) + perception.gradients["current"][1] * 0.8
        return Action("explore", angle_x, angle_y, 0.34 + self.genome.curiosity * 0.24, "habit", "low pressure exploration", 0.46).normalized()

    def should_deliberate(self, perception: Perception, rng: Random, *, global_enabled: bool) -> bool:
        if not global_enabled or self.model_budget <= 0 or self.deliberation_cooldown > 0:
            return False
        if self.last_decision.source == "reflex":
            return False
        pressure = max(self.hunger, self.fear, self.stress, self.reproductive_drive)
        uncertainty = 0.0
        if len({event["outcome"] for event in self.memory.events[-5:]}) >= 3:
            uncertainty += 0.16
        if perception.nearest_food[2] > self.genome.sensory_range and self.hunger > 0.58:
            uncertainty += 0.18
        if pressure > 0.62:
            uncertainty += 0.18
        chance = self.genome.deliberation_chance + uncertainty
        return rng.random() < chance

    def set_model_intent(self, action: Action, ttl: int) -> None:
        self.model_intent = action.normalized()
        self.model_intent_ttl = max(1, ttl)
        self.last_model_decision = self.model_intent
        self.model_pending = False

    def clear_model_pending(self) -> None:
        self.model_pending = False

    def record_outcome(self, tick: int, action: Action, *, outcome: str, delta_energy: float, delta_health: float) -> None:
        self.memory.record(tick, action, outcome=outcome, delta_energy=delta_energy, delta_health=delta_health)
        self.memory.trim(self.genome.memory_span)
        self.recent_outcomes.append(outcome)
        if len(self.recent_outcomes) > 8:
            del self.recent_outcomes[: len(self.recent_outcomes) - 8]
        self.last_decision = action

    def payload(self) -> dict[str, Any]:
        return {
            "id": self.fish_id,
            "species_id": self.species_id,
            "lineage": self.lineage_id,
            "generation": self.generation,
            "body_state": self.body_state,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "vx": round(self.vx, 3),
            "vy": round(self.vy, 3),
            "energy": round(self.energy, 3),
            "hunger": round(self.hunger, 3),
            "fear": round(self.fear, 3),
            "stress": round(self.stress, 3),
            "health": round(self.health, 3),
            "reproductive_drive": round(self.reproductive_drive, 3),
            "age": self.age,
            "radius": round(self.radius, 3),
            "model_budget": self.model_budget,
            "model_pending": self.model_pending,
            "model_intent_ttl": self.model_intent_ttl,
            "recent_outcomes": list(self.recent_outcomes[-5:]),
            "memory": self.memory.payload(),
            "genome": self.genome.payload(),
            "phenotype": self.genome.phenotype_payload(),
            "decision": self.last_decision.payload(),
            "active_intent": self.model_intent.payload() if self.model_intent else None,
            "last_model_decision": self.last_model_decision.payload() if self.last_model_decision else None,
            "perception": self.last_perception.payload() if self.last_perception else None,
        }

    def frame_payload(self) -> dict[str, Any]:
        return {
            "id": self.fish_id,
            "species_id": self.species_id,
            "lineage": self.lineage_id,
            "generation": self.generation,
            "body_state": self.body_state,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "vx": round(self.vx, 3),
            "vy": round(self.vy, 3),
            "energy": round(self.energy, 3),
            "hunger": round(self.hunger, 3),
            "fear": round(self.fear, 3),
            "stress": round(self.stress, 3),
            "health": round(self.health, 3),
            "reproductive_drive": round(self.reproductive_drive, 3),
            "age": self.age,
            "radius": round(self.radius, 3),
            "model_budget": self.model_budget,
            "model_pending": self.model_pending,
            "model_intent_ttl": self.model_intent_ttl,
            "genome": {
                "archetype": self.genome.archetype,
                "metabolism": self.genome.metabolism,
                "body_size": round(self.genome.body_size, 3),
                "max_speed": round(self.genome.max_speed, 3),
                "risk_tolerance": round(self.genome.risk_tolerance, 3),
                "aggression": round(self.genome.aggression, 3),
                "color": self.genome.color,
                "accent_color": self.genome.accent_color,
            },
            "phenotype": self.genome.phenotype_payload(compact=True),
            "decision": self.last_decision.payload(),
            "active_intent": self.model_intent.payload() if self.model_intent else None,
            "last_model_decision": self.last_model_decision.payload() if self.last_model_decision else None,
            "recent_outcomes": list(self.recent_outcomes[-3:]),
        }
