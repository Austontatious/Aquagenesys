from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from random import Random
from typing import Any


MORPHOLOGY_SCHEMA = "aquagenesys.morphology.v1"
AFFORDANCE_SCHEMA = "aquagenesys.morphology_affordances.v1"
MOUTH_POSITIONS = ("terminal", "ventral", "dorsal", "subterminal", "filter_slot")


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _round_payload(payload: dict[str, Any]) -> dict[str, Any]:
    rounded: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, float):
            rounded[key] = round(value, 3)
        elif isinstance(value, dict):
            rounded[key] = _round_payload(value)
        else:
            rounded[key] = value
    return rounded


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def stable_hash(payload: dict[str, Any], *, length: int = 16) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()[:length]


def _jitter(rng: Random, value: float, spread: float = 0.055, low: float = 0.0, high: float = 1.25) -> float:
    return clamp(value + rng.gauss(0.0, spread), low, high)


def _shift_enum(value: str, values: tuple[str, ...], rng: Random) -> str:
    if value not in values:
        return values[len(values) // 2]
    index = values.index(value)
    if rng.random() < 0.5:
        index += rng.choice((-1, 1))
    else:
        index = rng.randrange(len(values))
    return values[max(0, min(len(values) - 1, index))]


@dataclass(frozen=True)
class BodyScaffoldLoci:
    body_mass: float = 0.62
    body_length: float = 0.62
    body_depth: float = 0.52
    body_axis_length: float = 0.62
    body_axis_depth: float = 0.52
    surface_area: float = 0.55
    soft_tissue_ratio: float = 0.50
    reserve_capacity: float = 0.52


@dataclass(frozen=True)
class HeadMouthLoci:
    head_mass_ratio: float = 0.42
    mouth_position: str = "terminal"
    mouth_aperture: float = 0.46
    mouth_force: float = 0.38
    mouth_suction: float = 0.40
    gut_capacity: float = 0.48
    filter_surface_area: float = 0.34


@dataclass(frozen=True)
class AppendageLoci:
    appendage_count: int = 2
    appendage_length: float = 0.32
    appendage_flexibility: float = 0.42
    appendage_strength: float = 0.36
    propulsion_surface: float = 0.48


@dataclass(frozen=True)
class ArmorSkinLoci:
    armor_density: float = 0.22
    spine_density: float = 0.12
    tissue_vulnerability: float = 0.42
    mucous_barrier: float = 0.36


@dataclass(frozen=True)
class ChemicalLoci:
    chemical_gland_capacity: float = 0.06
    chemical_delivery_efficiency: float = 0.05
    toxin_resistance: float = 0.34
    self_toxicity: float = 0.08


@dataclass(frozen=True)
class SensoryLoci:
    sensory_surface_area: float = 0.45
    chemical_sensitivity: float = 0.42
    motion_sensitivity: float = 0.42
    visual_acuity: float = 0.38


@dataclass(frozen=True)
class DevelopmentLoci:
    developmental_stability: float = 0.72
    mutation_volatility: float = 0.14
    growth_cost: float = 0.36
    juvenile_fragility: float = 0.30
    reproduction_cost: float = 0.34
    oxygen_demand: float = 0.42


@dataclass(frozen=True)
class MorphologyGenome:
    schema: str = MORPHOLOGY_SCHEMA
    body: BodyScaffoldLoci = BodyScaffoldLoci()
    head_mouth: HeadMouthLoci = HeadMouthLoci()
    appendage: AppendageLoci = AppendageLoci()
    armor_skin: ArmorSkinLoci = ArmorSkinLoci()
    chemical: ChemicalLoci = ChemicalLoci()
    sensory: SensoryLoci = SensoryLoci()
    development: DevelopmentLoci = DevelopmentLoci()

    @classmethod
    def balanced(cls) -> "MorphologyGenome":
        return cls()

    @classmethod
    def founder(
        cls,
        rng: Random,
        *,
        archetype: str,
        body_size: float,
        body_depth: float,
        max_speed: float,
        turning: float,
        sensory_range: float,
        toxin_tolerance: float,
    ) -> "MorphologyGenome":
        body_mass = clamp(0.24 + body_size * 0.74 + rng.uniform(-0.04, 0.04), 0.12, 1.18)
        axis_length = clamp(0.24 + max_speed * 0.46 + body_size * 0.20 + rng.uniform(-0.04, 0.04), 0.12, 1.18)
        axis_depth = clamp(0.18 + body_depth * 0.64 + body_size * 0.10 + rng.uniform(-0.04, 0.04), 0.10, 1.18)
        surface = clamp((axis_length + axis_depth) * 0.42 + rng.uniform(-0.03, 0.03), 0.12, 1.18)
        body = BodyScaffoldLoci(
            body_mass=body_mass,
            body_length=axis_length,
            body_depth=axis_depth,
            body_axis_length=axis_length,
            body_axis_depth=axis_depth,
            surface_area=surface,
            soft_tissue_ratio=clamp(0.54 - body_depth * 0.18 + rng.uniform(-0.05, 0.05), 0.10, 1.05),
            reserve_capacity=clamp(0.26 + body_size * 0.42 + rng.uniform(-0.05, 0.05), 0.10, 1.12),
        )
        head = HeadMouthLoci(
            head_mass_ratio=clamp(0.30 + rng.uniform(-0.05, 0.05), 0.10, 1.10),
            mouth_position="terminal",
            mouth_aperture=clamp(0.34 + rng.uniform(-0.05, 0.05), 0.04, 1.10),
            mouth_force=clamp(0.32 + rng.uniform(-0.05, 0.05), 0.04, 1.10),
            mouth_suction=clamp(0.34 + rng.uniform(-0.05, 0.05), 0.04, 1.10),
            gut_capacity=clamp(0.38 + body_size * 0.25 + rng.uniform(-0.05, 0.05), 0.08, 1.15),
            filter_surface_area=clamp(0.24 + rng.uniform(-0.05, 0.05), 0.02, 1.10),
        )
        appendage = AppendageLoci(
            appendage_count=max(0, min(10, int(round(1 + turning * 3.0 + rng.choice((0, 1)))))),
            appendage_length=clamp(0.22 + turning * 0.22 + rng.uniform(-0.05, 0.05), 0.02, 1.10),
            appendage_flexibility=clamp(0.28 + turning * 0.34 + rng.uniform(-0.05, 0.05), 0.04, 1.10),
            appendage_strength=clamp(0.24 + body_size * 0.22 + rng.uniform(-0.05, 0.05), 0.04, 1.10),
            propulsion_surface=clamp(0.28 + max_speed * 0.44 + rng.uniform(-0.05, 0.05), 0.08, 1.15),
        )
        armor = ArmorSkinLoci(
            armor_density=clamp(0.16 + body_depth * 0.16 + rng.uniform(-0.04, 0.04), 0.02, 1.10),
            spine_density=clamp(0.08 + rng.uniform(-0.03, 0.04), 0.0, 1.10),
            tissue_vulnerability=clamp(0.46 - body_depth * 0.18 + rng.uniform(-0.05, 0.05), 0.06, 1.10),
            mucous_barrier=clamp(0.26 + toxin_tolerance * 0.22 + rng.uniform(-0.04, 0.04), 0.04, 1.10),
        )
        chemical = ChemicalLoci(
            chemical_gland_capacity=clamp(0.04 + toxin_tolerance * 0.08 + rng.uniform(-0.02, 0.04), 0.0, 1.0),
            chemical_delivery_efficiency=clamp(0.04 + rng.uniform(-0.02, 0.04), 0.0, 1.0),
            toxin_resistance=clamp(0.18 + toxin_tolerance * 0.62 + rng.uniform(-0.04, 0.04), 0.02, 1.15),
            self_toxicity=clamp(0.06 + rng.uniform(-0.02, 0.04), 0.0, 1.0),
        )
        sensory = SensoryLoci(
            sensory_surface_area=clamp(0.18 + sensory_range / 16.0 + rng.uniform(-0.04, 0.04), 0.08, 1.15),
            chemical_sensitivity=clamp(0.22 + sensory_range / 18.0 + rng.uniform(-0.04, 0.04), 0.05, 1.15),
            motion_sensitivity=clamp(0.22 + turning * 0.30 + rng.uniform(-0.04, 0.04), 0.05, 1.15),
            visual_acuity=clamp(0.24 + max_speed * 0.26 + rng.uniform(-0.04, 0.04), 0.05, 1.15),
        )
        development = DevelopmentLoci(
            developmental_stability=clamp(0.74 + rng.uniform(-0.08, 0.06), 0.25, 1.0),
            mutation_volatility=clamp(0.12 + rng.uniform(-0.04, 0.06), 0.02, 0.72),
            growth_cost=clamp(0.24 + body_mass * 0.18 + body_depth * 0.08, 0.08, 1.0),
            juvenile_fragility=clamp(0.22 + body_depth * 0.08 + rng.uniform(-0.04, 0.05), 0.04, 0.90),
            reproduction_cost=clamp(0.22 + body_mass * 0.12 + rng.uniform(-0.04, 0.05), 0.06, 0.95),
            oxygen_demand=clamp(0.25 + body_mass * 0.18 + max_speed * 0.08 + rng.uniform(-0.04, 0.05), 0.08, 1.0),
        )

        genome = cls(body=body, head_mouth=head, appendage=appendage, armor_skin=armor, chemical=chemical, sensory=sensory, development=development)
        return genome._specialize_founder(archetype)

    def _specialize_founder(self, archetype: str) -> "MorphologyGenome":
        if archetype == "glass_filter":
            return replace(
                self,
                body=replace(self.body, body_length=clamp(self.body.body_length + 0.16), body_axis_length=clamp(self.body.body_axis_length + 0.18), surface_area=clamp(self.body.surface_area + 0.14), soft_tissue_ratio=clamp(self.body.soft_tissue_ratio + 0.08)),
                head_mouth=replace(self.head_mouth, head_mass_ratio=clamp(self.head_mouth.head_mass_ratio - 0.08), mouth_position="filter_slot", mouth_suction=clamp(self.head_mouth.mouth_suction + 0.22), filter_surface_area=clamp(self.head_mouth.filter_surface_area + 0.34), gut_capacity=clamp(self.head_mouth.gut_capacity + 0.10), mouth_force=clamp(self.head_mouth.mouth_force - 0.08)),
                appendage=replace(self.appendage, appendage_count=max(1, self.appendage.appendage_count - 1), propulsion_surface=clamp(self.appendage.propulsion_surface + 0.14), appendage_length=clamp(self.appendage.appendage_length - 0.04)),
                armor_skin=replace(self.armor_skin, armor_density=clamp(self.armor_skin.armor_density - 0.06), tissue_vulnerability=clamp(self.armor_skin.tissue_vulnerability + 0.08)),
            )
        if archetype == "mud_stalker":
            return replace(
                self,
                body=replace(self.body, body_mass=clamp(self.body.body_mass + 0.14), body_depth=clamp(self.body.body_depth + 0.10), reserve_capacity=clamp(self.body.reserve_capacity + 0.10), soft_tissue_ratio=clamp(self.body.soft_tissue_ratio - 0.05)),
                head_mouth=replace(self.head_mouth, head_mass_ratio=clamp(self.head_mouth.head_mass_ratio + 0.30), mouth_aperture=clamp(self.head_mouth.mouth_aperture + 0.24), mouth_force=clamp(self.head_mouth.mouth_force + 0.34), mouth_suction=clamp(self.head_mouth.mouth_suction - 0.02), filter_surface_area=clamp(self.head_mouth.filter_surface_area - 0.12)),
                appendage=replace(self.appendage, appendage_strength=clamp(self.appendage.appendage_strength + 0.12), appendage_flexibility=clamp(self.appendage.appendage_flexibility - 0.04)),
                armor_skin=replace(self.armor_skin, armor_density=clamp(self.armor_skin.armor_density + 0.08), spine_density=clamp(self.armor_skin.spine_density + 0.08)),
                development=replace(self.development, growth_cost=clamp(self.development.growth_cost + 0.10), juvenile_fragility=clamp(self.development.juvenile_fragility + 0.10), reproduction_cost=clamp(self.development.reproduction_cost + 0.08), oxygen_demand=clamp(self.development.oxygen_demand + 0.08)),
            )
        if archetype == "silt_grazer":
            return replace(
                self,
                body=replace(self.body, body_mass=clamp(self.body.body_mass + 0.06), body_depth=clamp(self.body.body_depth + 0.08), reserve_capacity=clamp(self.body.reserve_capacity + 0.18)),
                head_mouth=replace(self.head_mouth, mouth_position="ventral", head_mass_ratio=clamp(self.head_mouth.head_mass_ratio - 0.04), mouth_aperture=clamp(self.head_mouth.mouth_aperture + 0.04), mouth_force=clamp(self.head_mouth.mouth_force + 0.08), gut_capacity=clamp(self.head_mouth.gut_capacity + 0.24), filter_surface_area=clamp(self.head_mouth.filter_surface_area + 0.08)),
                armor_skin=replace(self.armor_skin, armor_density=clamp(self.armor_skin.armor_density + 0.04), tissue_vulnerability=clamp(self.armor_skin.tissue_vulnerability - 0.04)),
            )
        if archetype == "reed_sprinter":
            return replace(
                self,
                body=replace(self.body, body_length=clamp(self.body.body_length + 0.18), body_axis_length=clamp(self.body.body_axis_length + 0.18), body_axis_depth=clamp(self.body.body_axis_depth - 0.06), body_depth=clamp(self.body.body_depth - 0.04)),
                appendage=replace(self.appendage, propulsion_surface=clamp(self.appendage.propulsion_surface + 0.28), appendage_flexibility=clamp(self.appendage.appendage_flexibility + 0.10), appendage_strength=clamp(self.appendage.appendage_strength - 0.02)),
                sensory=replace(self.sensory, motion_sensitivity=clamp(self.sensory.motion_sensitivity + 0.12), visual_acuity=clamp(self.sensory.visual_acuity + 0.10)),
                development=replace(self.development, oxygen_demand=clamp(self.development.oxygen_demand + 0.05)),
            )
        return self

    @property
    def morphology_hash(self) -> str:
        payload = self.payload(include_hash=False)
        return f"morph_{stable_hash(payload, length=12)}"

    def payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload = {
            "schema": self.schema,
            "body": asdict(self.body),
            "head_mouth": asdict(self.head_mouth),
            "appendage": asdict(self.appendage),
            "armor_skin": asdict(self.armor_skin),
            "chemical": asdict(self.chemical),
            "sensory": asdict(self.sensory),
            "development": asdict(self.development),
        }
        rounded = _round_payload(payload)
        if include_hash:
            rounded["morphology_hash"] = self.morphology_hash
        return rounded

    def loci_summary(self) -> dict[str, str]:
        return morphology_loci_summary(self)

    def mutated(self, rng: Random, *, mutation_load: float = 0.0) -> "MorphologyGenome":
        spread = 0.026 + self.development.mutation_volatility * 0.028 + mutation_load * 0.018

        body = BodyScaffoldLoci(**{key: _jitter(rng, value, spread) for key, value in asdict(self.body).items()})
        head_raw = asdict(self.head_mouth)
        head = HeadMouthLoci(
            **{
                key: (_shift_enum(value, MOUTH_POSITIONS, rng) if key == "mouth_position" and rng.random() < 0.015 + mutation_load * 0.02 else value if key == "mouth_position" else _jitter(rng, value, spread))
                for key, value in head_raw.items()
            }
        )
        appendage = AppendageLoci(
            appendage_count=max(0, min(14, int(round(self.appendage.appendage_count + rng.choice((-1, 0, 0, 0, 1)) + rng.gauss(0.0, self.development.mutation_volatility * 0.65))))),
            appendage_length=_jitter(rng, self.appendage.appendage_length, spread),
            appendage_flexibility=_jitter(rng, self.appendage.appendage_flexibility, spread),
            appendage_strength=_jitter(rng, self.appendage.appendage_strength, spread),
            propulsion_surface=_jitter(rng, self.appendage.propulsion_surface, spread),
        )
        armor = ArmorSkinLoci(**{key: _jitter(rng, value, spread) for key, value in asdict(self.armor_skin).items()})
        chemical = ChemicalLoci(**{key: _jitter(rng, value, spread) for key, value in asdict(self.chemical).items()})
        sensory = SensoryLoci(**{key: _jitter(rng, value, spread) for key, value in asdict(self.sensory).items()})
        development = DevelopmentLoci(
            developmental_stability=_jitter(rng, self.development.developmental_stability, spread * 0.65, 0.08, 1.0),
            mutation_volatility=_jitter(rng, self.development.mutation_volatility, spread * 0.55, 0.01, 0.90),
            growth_cost=_jitter(rng, self.development.growth_cost, spread),
            juvenile_fragility=_jitter(rng, self.development.juvenile_fragility, spread),
            reproduction_cost=_jitter(rng, self.development.reproduction_cost, spread),
            oxygen_demand=_jitter(rng, self.development.oxygen_demand, spread),
        )
        genome = MorphologyGenome(
            body=body,
            head_mouth=head,
            appendage=appendage,
            armor_skin=armor,
            chemical=chemical,
            sensory=sensory,
            development=development,
        )
        mutation_roll = 0.050 + self.development.mutation_volatility * 0.11 + mutation_load * 0.025
        if rng.random() < mutation_roll:
            genome = genome._module_shift(rng)
        if rng.random() < mutation_roll * 0.30:
            genome = genome._module_shift(rng)
        return genome

    def _module_shift(self, rng: Random) -> "MorphologyGenome":
        shift = rng.choice(("appendage_amplification", "appendage_reduction", "head_specialization", "filter_specialization", "armor_amplification", "chemical_duplication", "soft_body_shift", "sensory_expansion", "developmental_instability"))
        if shift == "appendage_amplification":
            return replace(
                self,
                appendage=replace(
                    self.appendage,
                    appendage_count=max(0, min(14, self.appendage.appendage_count + rng.randint(1, 3))),
                    appendage_length=clamp(self.appendage.appendage_length + rng.uniform(0.06, 0.18), 0.0, 1.35),
                    appendage_flexibility=clamp(self.appendage.appendage_flexibility + rng.uniform(0.03, 0.14), 0.0, 1.35),
                    appendage_strength=clamp(self.appendage.appendage_strength + rng.uniform(0.02, 0.10), 0.0, 1.35),
                ),
                armor_skin=replace(self.armor_skin, tissue_vulnerability=clamp(self.armor_skin.tissue_vulnerability + rng.uniform(0.02, 0.10), 0.0, 1.25)),
                development=replace(self.development, growth_cost=clamp(self.development.growth_cost + rng.uniform(0.03, 0.11), 0.0, 1.25), oxygen_demand=clamp(self.development.oxygen_demand + rng.uniform(0.02, 0.08), 0.0, 1.25)),
            )
        if shift == "appendage_reduction":
            return replace(
                self,
                appendage=replace(
                    self.appendage,
                    appendage_count=max(0, self.appendage.appendage_count - rng.randint(1, 3)),
                    appendage_length=clamp(self.appendage.appendage_length - rng.uniform(0.04, 0.14), 0.0, 1.35),
                    appendage_flexibility=clamp(self.appendage.appendage_flexibility - rng.uniform(0.02, 0.10), 0.0, 1.35),
                ),
                development=replace(self.development, growth_cost=clamp(self.development.growth_cost - rng.uniform(0.02, 0.07), 0.0, 1.25)),
            )
        if shift == "head_specialization":
            return replace(
                self,
                head_mouth=replace(
                    self.head_mouth,
                    head_mass_ratio=clamp(self.head_mouth.head_mass_ratio + rng.uniform(0.08, 0.22), 0.0, 1.35),
                    mouth_aperture=clamp(self.head_mouth.mouth_aperture + rng.uniform(0.05, 0.18), 0.0, 1.35),
                    mouth_force=clamp(self.head_mouth.mouth_force + rng.uniform(0.08, 0.24), 0.0, 1.35),
                ),
                development=replace(self.development, juvenile_fragility=clamp(self.development.juvenile_fragility + rng.uniform(0.03, 0.12), 0.0, 1.25), oxygen_demand=clamp(self.development.oxygen_demand + rng.uniform(0.03, 0.10), 0.0, 1.25), reproduction_cost=clamp(self.development.reproduction_cost + rng.uniform(0.02, 0.08), 0.0, 1.25)),
            )
        if shift == "filter_specialization":
            return replace(
                self,
                head_mouth=replace(
                    self.head_mouth,
                    mouth_position="filter_slot",
                    mouth_suction=clamp(self.head_mouth.mouth_suction + rng.uniform(0.07, 0.20), 0.0, 1.35),
                    filter_surface_area=clamp(self.head_mouth.filter_surface_area + rng.uniform(0.10, 0.26), 0.0, 1.35),
                    gut_capacity=clamp(self.head_mouth.gut_capacity + rng.uniform(0.04, 0.14), 0.0, 1.35),
                    mouth_force=clamp(self.head_mouth.mouth_force - rng.uniform(0.02, 0.08), 0.0, 1.35),
                ),
                development=replace(self.development, oxygen_demand=clamp(self.development.oxygen_demand + rng.uniform(0.02, 0.08), 0.0, 1.25)),
            )
        if shift == "armor_amplification":
            return replace(
                self,
                armor_skin=replace(self.armor_skin, armor_density=clamp(self.armor_skin.armor_density + rng.uniform(0.08, 0.22), 0.0, 1.35), spine_density=clamp(self.armor_skin.spine_density + rng.uniform(0.03, 0.16), 0.0, 1.35), tissue_vulnerability=clamp(self.armor_skin.tissue_vulnerability - rng.uniform(0.03, 0.12), 0.0, 1.35)),
                development=replace(self.development, growth_cost=clamp(self.development.growth_cost + rng.uniform(0.03, 0.12), 0.0, 1.25), reproduction_cost=clamp(self.development.reproduction_cost + rng.uniform(0.03, 0.10), 0.0, 1.25), oxygen_demand=clamp(self.development.oxygen_demand + rng.uniform(0.02, 0.08), 0.0, 1.25)),
            )
        if shift == "chemical_duplication":
            return replace(
                self,
                chemical=replace(self.chemical, chemical_gland_capacity=clamp(self.chemical.chemical_gland_capacity + rng.uniform(0.08, 0.24), 0.0, 1.35), chemical_delivery_efficiency=clamp(self.chemical.chemical_delivery_efficiency + rng.uniform(0.04, 0.18), 0.0, 1.35), toxin_resistance=clamp(self.chemical.toxin_resistance + rng.uniform(0.02, 0.12), 0.0, 1.35), self_toxicity=clamp(self.chemical.self_toxicity + rng.uniform(0.04, 0.16), 0.0, 1.35)),
                development=replace(self.development, growth_cost=clamp(self.development.growth_cost + rng.uniform(0.02, 0.08), 0.0, 1.25), reproduction_cost=clamp(self.development.reproduction_cost + rng.uniform(0.02, 0.08), 0.0, 1.25)),
            )
        if shift == "soft_body_shift":
            return replace(
                self,
                body=replace(self.body, soft_tissue_ratio=clamp(self.body.soft_tissue_ratio + rng.uniform(0.08, 0.22), 0.0, 1.35), surface_area=clamp(self.body.surface_area + rng.uniform(0.03, 0.12), 0.0, 1.35)),
                armor_skin=replace(self.armor_skin, armor_density=clamp(self.armor_skin.armor_density - rng.uniform(0.03, 0.12), 0.0, 1.35), tissue_vulnerability=clamp(self.armor_skin.tissue_vulnerability + rng.uniform(0.05, 0.16), 0.0, 1.35)),
                development=replace(self.development, growth_cost=clamp(self.development.growth_cost - rng.uniform(0.02, 0.08), 0.0, 1.25), juvenile_fragility=clamp(self.development.juvenile_fragility + rng.uniform(0.03, 0.12), 0.0, 1.25)),
            )
        if shift == "sensory_expansion":
            return replace(
                self,
                sensory=replace(self.sensory, sensory_surface_area=clamp(self.sensory.sensory_surface_area + rng.uniform(0.08, 0.22), 0.0, 1.35), chemical_sensitivity=clamp(self.sensory.chemical_sensitivity + rng.uniform(0.05, 0.18), 0.0, 1.35), motion_sensitivity=clamp(self.sensory.motion_sensitivity + rng.uniform(0.05, 0.18), 0.0, 1.35), visual_acuity=clamp(self.sensory.visual_acuity + rng.uniform(0.03, 0.14), 0.0, 1.35)),
                development=replace(self.development, oxygen_demand=clamp(self.development.oxygen_demand + rng.uniform(0.02, 0.09), 0.0, 1.25), growth_cost=clamp(self.development.growth_cost + rng.uniform(0.01, 0.06), 0.0, 1.25)),
            )
        return replace(
            self,
            development=replace(
                self.development,
                developmental_stability=clamp(self.development.developmental_stability - rng.uniform(0.08, 0.22), 0.0, 1.0),
                mutation_volatility=clamp(self.development.mutation_volatility + rng.uniform(0.05, 0.20), 0.0, 1.0),
                juvenile_fragility=clamp(self.development.juvenile_fragility + rng.uniform(0.04, 0.14), 0.0, 1.25),
            ),
        )


@dataclass(frozen=True)
class MorphologyAffordances:
    schema: str
    morphology_hash: str
    reach: float
    grip: float
    strike_impulse: float
    bite_force: float
    suction_force: float
    filter_rate: float
    scrape_rate: float
    armor_protection: float
    tissue_vulnerability: float
    toxin_payload: float
    toxin_delivery: float
    toxin_resistance: float
    toxin_self_cost: float
    sensory_range: float
    chemical_sense: float
    motion_sense: float
    drag: float
    thrust_modifier: float
    turn_penalty: float
    oxygen_cost: float
    metabolic_burden: float
    growth_cost: float
    reproduction_cost: float
    juvenile_fragility: float
    feeding_throughput: float
    predation_risk_modifier: float
    viability_index: float

    def payload(self) -> dict[str, Any]:
        return _round_payload(asdict(self))

    def compact_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "morphology_hash": self.morphology_hash,
            "reach": round(self.reach, 3),
            "grip": round(self.grip, 3),
            "bite_force": round(self.bite_force, 3),
            "suction_force": round(self.suction_force, 3),
            "filter_rate": round(self.filter_rate, 3),
            "armor_protection": round(self.armor_protection, 3),
            "toxin_payload": round(self.toxin_payload, 3),
            "sensory_range": round(self.sensory_range, 3),
            "drag": round(self.drag, 3),
            "oxygen_cost": round(self.oxygen_cost, 3),
            "metabolic_burden": round(self.metabolic_burden, 3),
            "feeding_throughput": round(self.feeding_throughput, 3),
            "predation_risk_modifier": round(self.predation_risk_modifier, 3),
            "viability_index": round(self.viability_index, 3),
        }


def interpret_morphology(morphology: MorphologyGenome) -> MorphologyAffordances:
    body = morphology.body
    head = morphology.head_mouth
    appendage = morphology.appendage
    skin = morphology.armor_skin
    chemical = morphology.chemical
    sensory = morphology.sensory
    development = morphology.development

    appendage_expression = clamp(appendage.appendage_count / 10.0, 0.0, 1.35)
    appendage_load = clamp(appendage_expression * appendage.appendage_length * (0.65 + appendage.appendage_strength * 0.45), 0.0, 1.55)
    softness = clamp(body.soft_tissue_ratio * 0.62 + skin.tissue_vulnerability * 0.38)
    head_extreme = max(0.0, head.head_mass_ratio - 0.68) + max(0.0, 0.22 - head.head_mass_ratio) * 0.55

    reach = clamp(appendage_expression * 0.23 + appendage.appendage_length * 0.42 + appendage.appendage_flexibility * 0.20 + body.body_axis_length * 0.07, 0.0, 1.35)
    grip = clamp(appendage_expression * 0.18 + appendage.appendage_length * 0.12 + appendage.appendage_flexibility * 0.20 + appendage.appendage_strength * 0.36 - softness * 0.06, 0.0, 1.35)
    armor_protection = clamp(skin.armor_density * 0.56 + skin.spine_density * 0.19 + skin.mucous_barrier * 0.09 + body.body_mass * 0.08 - softness * 0.12, 0.0, 1.35)
    tissue_vulnerability = clamp(skin.tissue_vulnerability * 0.44 + body.soft_tissue_ratio * 0.32 + appendage_load * 0.10 - armor_protection * 0.22 - skin.mucous_barrier * 0.08, 0.0, 1.35)
    toxin_payload = clamp(chemical.chemical_gland_capacity * 0.58 + chemical.chemical_delivery_efficiency * 0.18, 0.0, 1.35)
    toxin_delivery = clamp(chemical.chemical_delivery_efficiency * 0.50 + skin.spine_density * 0.11 + appendage.appendage_strength * 0.08 + head.mouth_force * 0.10, 0.0, 1.35)
    toxin_resistance = clamp(chemical.toxin_resistance * 0.74 + skin.mucous_barrier * 0.18, 0.0, 1.35)
    toxin_self_cost = clamp(chemical.self_toxicity * 0.45 + chemical.chemical_gland_capacity * 0.25 - toxin_resistance * 0.28, 0.0, 1.35)

    drag = clamp(
        body.body_depth * 0.24
        + body.body_mass * 0.18
        + appendage_load * 0.22
        + skin.armor_density * 0.13
        + skin.spine_density * 0.08
        + head.head_mass_ratio * 0.08
        - appendage.propulsion_surface * 0.09,
        0.0,
        1.55,
    )
    thrust_modifier = clamp(0.54 + appendage.propulsion_surface * 0.36 + body.body_axis_length * 0.08 + appendage.appendage_strength * 0.04 - drag * 0.20, 0.22, 1.35)
    turn_penalty = clamp(body.body_depth * 0.21 + body.body_mass * 0.14 + head.head_mass_ratio * 0.15 + appendage_load * 0.18 + skin.armor_density * 0.10 - appendage.appendage_flexibility * 0.10, 0.0, 1.35)

    strike_impulse = clamp(head.mouth_force * 0.35 + head.head_mass_ratio * 0.24 + body.body_mass * 0.11 + thrust_modifier * 0.14 + reach * 0.05 - turn_penalty * 0.08, 0.0, 1.35)
    bite_force = clamp(head.head_mass_ratio * 0.32 + head.mouth_force * 0.45 + head.mouth_aperture * 0.16 + body.body_mass * 0.06 - body.soft_tissue_ratio * 0.05, 0.0, 1.35)
    suction_force = clamp(head.mouth_suction * 0.50 + head.mouth_aperture * 0.16 + head.filter_surface_area * 0.09 + head.head_mass_ratio * 0.08 - body.body_depth * 0.04, 0.0, 1.35)
    filter_rate = clamp(head.filter_surface_area * 0.52 + suction_force * 0.20 + head.gut_capacity * 0.16 + body.surface_area * 0.07 - head.mouth_force * 0.04, 0.0, 1.35)
    ventral_bonus = 0.10 if head.mouth_position == "ventral" else 0.04 if head.mouth_position == "subterminal" else 0.0
    scrape_rate = clamp(head.mouth_force * 0.23 + head.gut_capacity * 0.14 + grip * 0.15 + ventral_bonus + skin.armor_density * 0.04, 0.0, 1.35)

    chemical_sense = clamp(sensory.chemical_sensitivity * 0.62 + sensory.sensory_surface_area * 0.20 + head.filter_surface_area * 0.04, 0.0, 1.35)
    motion_sense = clamp(sensory.motion_sensitivity * 0.62 + sensory.visual_acuity * 0.16 + appendage.appendage_flexibility * 0.05, 0.0, 1.35)
    sensory_range = clamp(sensory.sensory_surface_area * 0.34 + chemical_sense * 0.24 + motion_sense * 0.24 + sensory.visual_acuity * 0.14, 0.0, 1.35)

    oxygen_cost = clamp(development.oxygen_demand * 0.30 + body.body_mass * 0.16 + drag * 0.18 + head.head_mass_ratio * 0.07 + sensory.sensory_surface_area * 0.06 + chemical.chemical_gland_capacity * 0.06, 0.0, 1.35)
    growth_cost = clamp(development.growth_cost * 0.34 + body.body_mass * 0.12 + appendage_load * 0.15 + skin.armor_density * 0.13 + chemical.chemical_gland_capacity * 0.07 + head_extreme * 0.08, 0.0, 1.35)
    reproduction_cost = clamp(development.reproduction_cost * 0.36 + body.body_mass * 0.11 + head.head_mass_ratio * 0.07 + skin.armor_density * 0.08 + chemical.chemical_gland_capacity * 0.07 + appendage_load * 0.07, 0.0, 1.35)
    juvenile_fragility = clamp(development.juvenile_fragility * 0.38 + tissue_vulnerability * 0.15 + appendage_load * 0.12 + head_extreme * 0.13 + (1.0 - development.developmental_stability) * 0.22, 0.0, 1.35)
    metabolic_burden = clamp(oxygen_cost * 0.38 + growth_cost * 0.20 + reproduction_cost * 0.15 + toxin_self_cost * 0.12 + sensory_range * 0.05 + drag * 0.08, 0.0, 1.35)

    feeding_throughput = clamp(
        max(
            filter_rate * 0.82 + suction_force * 0.10,
            scrape_rate * 0.76 + head.gut_capacity * 0.12,
            bite_force * 0.62 + strike_impulse * 0.13 + head.gut_capacity * 0.08,
            reach * 0.24 + grip * 0.22 + head.gut_capacity * 0.16,
        ),
        0.0,
        1.35,
    )
    predation_risk_modifier = clamp(1.0 + tissue_vulnerability * 0.36 + drag * 0.14 - armor_protection * 0.38 - skin.spine_density * 0.13 - toxin_payload * toxin_delivery * 0.16 - body.body_mass * 0.08, 0.35, 1.65)

    support = 0.30 + feeding_throughput * 0.25 + armor_protection * 0.08 + sensory_range * 0.07 + thrust_modifier * 0.07 + toxin_resistance * 0.04 + body.reserve_capacity * 0.05
    mismatch_penalty = (
        max(0.0, body.body_mass - feeding_throughput - 0.24) * 0.15
        + max(0.0, head.head_mass_ratio - bite_force - suction_force - 0.25) * 0.13
        + max(0.0, appendage_load - grip - 0.20) * 0.12
        + max(0.0, toxin_payload - toxin_resistance - 0.18) * 0.12
    )
    penalty = metabolic_burden * 0.22 + growth_cost * 0.10 + reproduction_cost * 0.10 + juvenile_fragility * 0.13 + turn_penalty * 0.06 + toxin_self_cost * 0.10 + (1.0 - development.developmental_stability) * 0.13 + mismatch_penalty
    viability_index = clamp(support - penalty + 0.30, 0.02, 1.0)

    return MorphologyAffordances(
        schema=AFFORDANCE_SCHEMA,
        morphology_hash=morphology.morphology_hash,
        reach=reach,
        grip=grip,
        strike_impulse=strike_impulse,
        bite_force=bite_force,
        suction_force=suction_force,
        filter_rate=filter_rate,
        scrape_rate=scrape_rate,
        armor_protection=armor_protection,
        tissue_vulnerability=tissue_vulnerability,
        toxin_payload=toxin_payload,
        toxin_delivery=toxin_delivery,
        toxin_resistance=toxin_resistance,
        toxin_self_cost=toxin_self_cost,
        sensory_range=sensory_range,
        chemical_sense=chemical_sense,
        motion_sense=motion_sense,
        drag=drag,
        thrust_modifier=thrust_modifier,
        turn_penalty=turn_penalty,
        oxygen_cost=oxygen_cost,
        metabolic_burden=metabolic_burden,
        growth_cost=growth_cost,
        reproduction_cost=reproduction_cost,
        juvenile_fragility=juvenile_fragility,
        feeding_throughput=feeding_throughput,
        predation_risk_modifier=predation_risk_modifier,
        viability_index=viability_index,
    )


def morphology_loci_summary(morphology: MorphologyGenome) -> dict[str, str]:
    body = morphology.body
    head = morphology.head_mouth
    appendage = morphology.appendage
    skin = morphology.armor_skin
    chemical = morphology.chemical
    sensory = morphology.sensory
    development = morphology.development
    return {
        "body": f"mass {body.body_mass:.2f}, axis {body.body_axis_length:.2f}x{body.body_axis_depth:.2f}, soft tissue {body.soft_tissue_ratio:.2f}",
        "head_mouth": f"head {head.head_mass_ratio:.2f}, {head.mouth_position} mouth, aperture {head.mouth_aperture:.2f}, force {head.mouth_force:.2f}, suction {head.mouth_suction:.2f}, filter {head.filter_surface_area:.2f}",
        "appendage": f"{appendage.appendage_count} appendages, length {appendage.appendage_length:.2f}, flexibility {appendage.appendage_flexibility:.2f}, strength {appendage.appendage_strength:.2f}",
        "armor_skin": f"armor {skin.armor_density:.2f}, spines {skin.spine_density:.2f}, vulnerability {skin.tissue_vulnerability:.2f}, mucous {skin.mucous_barrier:.2f}",
        "chemical": f"gland {chemical.chemical_gland_capacity:.2f}, delivery {chemical.chemical_delivery_efficiency:.2f}, resistance {chemical.toxin_resistance:.2f}, self toxicity {chemical.self_toxicity:.2f}",
        "sensory": f"surface {sensory.sensory_surface_area:.2f}, chemical {sensory.chemical_sensitivity:.2f}, motion {sensory.motion_sensitivity:.2f}, visual {sensory.visual_acuity:.2f}",
        "development": f"stability {development.developmental_stability:.2f}, volatility {development.mutation_volatility:.2f}, growth {development.growth_cost:.2f}, juvenile fragility {development.juvenile_fragility:.2f}",
    }


def derive_observational_labels(morphology: MorphologyGenome, affordances: MorphologyAffordances | None = None) -> list[str]:
    aff = affordances or interpret_morphology(morphology)
    labels: list[str] = []
    appendage = morphology.appendage
    body = morphology.body
    head = morphology.head_mouth
    if appendage.appendage_count >= 6 and aff.reach >= 0.62:
        labels.append("appendage-rich soft-bodied organism" if body.soft_tissue_ratio >= 0.52 else "appendage-rich manipulator")
    if head.head_mass_ratio >= 0.66 and aff.bite_force >= 0.62:
        labels.append("large-headed bite specialist")
    if head.head_mass_ratio <= 0.30 and body.body_mass >= 0.70 and aff.filter_rate >= 0.58:
        labels.append("tiny-headed bulk filterer")
    if body.body_mass >= 0.78 and aff.filter_rate >= 0.62:
        labels.append("bulk-bodied filter grazer")
    if aff.suction_force >= 0.64 and head.mouth_suction >= head.mouth_force:
        labels.append("suction-feeding drifter")
    if aff.armor_protection >= 0.58 and aff.drag >= 0.46:
        labels.append("armored low-mobility grazer")
    if aff.toxin_payload >= 0.32 and aff.toxin_delivery >= 0.22:
        labels.append("chemical-defense specialist")
    if body.soft_tissue_ratio >= 0.66 and aff.armor_protection < 0.34:
        labels.append("soft-bodied scavenger-like organism")
    if not labels:
        if aff.filter_rate >= max(aff.bite_force, aff.scrape_rate):
            labels.append("filter-capable aquatic organism")
        elif aff.bite_force >= max(aff.filter_rate, aff.scrape_rate):
            labels.append("force-mouthed aquatic organism")
        elif aff.scrape_rate >= 0.44:
            labels.append("scraping grazer-like organism")
        else:
            labels.append("generalized aquatic body plan")
    return labels[:4]


def morphology_render_payload(morphology: MorphologyGenome, affordances: MorphologyAffordances | None = None) -> dict[str, Any]:
    aff = affordances or interpret_morphology(morphology)
    body = morphology.body
    head = morphology.head_mouth
    appendage = morphology.appendage
    skin = morphology.armor_skin
    chemical = morphology.chemical
    sensory = morphology.sensory
    mouth_shape = "filter_slot" if head.filter_surface_area >= max(head.mouth_force, head.mouth_aperture) else "suction" if head.mouth_suction >= head.mouth_force + 0.08 else "force_aperture" if head.mouth_force >= 0.56 else "small"
    return {
        "schema": MORPHOLOGY_SCHEMA,
        "morphology_hash": morphology.morphology_hash,
        "label": derive_observational_labels(morphology, aff)[0],
        "body_mass": round(body.body_mass, 3),
        "body_axis_length": round(body.body_axis_length, 3),
        "body_axis_depth": round(body.body_axis_depth, 3),
        "head_scale": round(0.58 + head.head_mass_ratio * 0.76, 3),
        "mouth_scale": round(0.36 + max(head.mouth_aperture, head.mouth_suction, head.filter_surface_area) * 0.62, 3),
        "mouth_shape": mouth_shape,
        "appendage_count": appendage.appendage_count,
        "appendage_length": round(appendage.appendage_length, 3),
        "appendage_flexibility": round(appendage.appendage_flexibility, 3),
        "appendage_strength": round(appendage.appendage_strength, 3),
        "armor_density": round(skin.armor_density, 3),
        "spine_density": round(skin.spine_density, 3),
        "soft_tissue_ratio": round(body.soft_tissue_ratio, 3),
        "chemical_marker": round(max(chemical.chemical_gland_capacity, aff.toxin_payload), 3),
        "sensory_surface": round(sensory.sensory_surface_area, 3),
        "viability_index": round(aff.viability_index, 3),
    }


def morphology_state_payload(*, organism_id: int, lineage_id: int, morphology: MorphologyGenome) -> dict[str, Any]:
    affordances = interpret_morphology(morphology)
    return {
        "id": f"fish-{organism_id}",
        "lineage_id": f"L{lineage_id}",
        "morphology_hash": morphology.morphology_hash,
        "loci_summary": morphology.loci_summary(),
        "affordances": affordances.compact_payload(),
        "labels": derive_observational_labels(morphology, affordances),
    }
