from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GeneFamily(str, Enum):
    STRUCTURE = "STRUCTURE"
    MOTION = "MOTION"
    SENSING = "SENSING"
    METABOLISM = "METABOLISM"
    ENERGY = "ENERGY"
    REPRODUCTION = "REPRODUCTION"
    TRANSFER = "TRANSFER"
    BEHAVIOR = "BEHAVIOR"
    REGULATION = "REGULATION"
    ROBUSTNESS = "ROBUSTNESS"


@dataclass(frozen=True)
class GenePrimitive:
    name: str
    family: GeneFamily
    optimum: int
    high: int
    extreme: int
    dominance: float = 0.5
    base_cost: float = 0.03


def primitive(
    name: str,
    family: GeneFamily,
    optimum: int = 3,
    high: int = 7,
    extreme: int = 12,
    dominance: float = 0.5,
    base_cost: float = 0.03,
) -> GenePrimitive:
    return GenePrimitive(
        name=name,
        family=family,
        optimum=optimum,
        high=high,
        extreme=extreme,
        dominance=dominance,
        base_cost=base_cost,
    )


PRIMITIVES: dict[str, GenePrimitive] = {
    # STRUCTURE
    "size": primitive("size", GeneFamily.STRUCTURE, 4, 9, 15, dominance=0.65, base_cost=0.07),
    "symmetry": primitive("symmetry", GeneFamily.STRUCTURE, 3, 8, 13, dominance=0.55, base_cost=0.03),
    "segmentation": primitive("segmentation", GeneFamily.STRUCTURE, 3, 7, 12, base_cost=0.04),
    "membrane": primitive("membrane", GeneFamily.STRUCTURE, 3, 8, 13, dominance=0.6, base_cost=0.06),
    "appendage": primitive("appendage", GeneFamily.STRUCTURE, 3, 7, 12, dominance=0.45, base_cost=0.06),
    "irregularity": primitive("irregularity", GeneFamily.STRUCTURE, 1, 4, 9, dominance=0.4, base_cost=0.04),
    # MOTION
    "contractility": primitive("contractility", GeneFamily.MOTION, 3, 8, 13, base_cost=0.07),
    "cilia": primitive("cilia", GeneFamily.MOTION, 3, 7, 12, base_cost=0.05),
    "tail_leverage": primitive("tail_leverage", GeneFamily.MOTION, 3, 8, 13, dominance=0.55, base_cost=0.08),
    "burst": primitive("burst", GeneFamily.MOTION, 2, 6, 11, base_cost=0.08),
    "turning": primitive("turning", GeneFamily.MOTION, 3, 7, 12, base_cost=0.04),
    # SENSING
    "sense_light": primitive("sense_light", GeneFamily.SENSING, 2, 6, 10, base_cost=0.03),
    "sense_heat": primitive("sense_heat", GeneFamily.SENSING, 2, 6, 10, base_cost=0.03),
    "sense_chem": primitive("sense_chem", GeneFamily.SENSING, 3, 8, 13, base_cost=0.04),
    "sense_touch": primitive("sense_touch", GeneFamily.SENSING, 2, 6, 10, base_cost=0.03),
    "sense_kin": primitive("sense_kin", GeneFamily.SENSING, 2, 5, 9, dominance=0.4, base_cost=0.03),
    "sense_threat": primitive("sense_threat", GeneFamily.SENSING, 2, 6, 10, base_cost=0.04),
    # METABOLISM
    "photosynthesis": primitive("photosynthesis", GeneFamily.METABOLISM, 4, 9, 15, dominance=0.45, base_cost=0.08),
    "chemosynthesis": primitive("chemosynthesis", GeneFamily.METABOLISM, 4, 9, 15, dominance=0.45, base_cost=0.08),
    "grazing": primitive("grazing", GeneFamily.METABOLISM, 3, 8, 13, dominance=0.55, base_cost=0.05),
    "predation": primitive("predation", GeneFamily.METABOLISM, 3, 7, 12, dominance=0.35, base_cost=0.1),
    "scavenging": primitive("scavenging", GeneFamily.METABOLISM, 3, 7, 12, base_cost=0.05),
    "low_o2": primitive("low_o2", GeneFamily.METABOLISM, 3, 7, 12, dominance=0.6, base_cost=0.05),
    # ENERGY
    "storage": primitive("storage", GeneFamily.ENERGY, 3, 8, 13, base_cost=0.05),
    "basal_burn": primitive("basal_burn", GeneFamily.ENERGY, 2, 5, 10, dominance=0.65, base_cost=0.02),
    "repair": primitive("repair", GeneFamily.ENERGY, 2, 6, 11, base_cost=0.06),
    "movement_efficiency": primitive("movement_efficiency", GeneFamily.ENERGY, 3, 8, 13, dominance=0.6, base_cost=0.03),
    "growth_cost": primitive("growth_cost", GeneFamily.ENERGY, 2, 6, 11, dominance=0.4, base_cost=0.03),
    # REPRODUCTION
    "budding": primitive("budding", GeneFamily.REPRODUCTION, 3, 8, 13, dominance=0.55, base_cost=0.05),
    "spores": primitive("spores", GeneFamily.REPRODUCTION, 3, 8, 13, base_cost=0.06),
    "sexual": primitive("sexual", GeneFamily.REPRODUCTION, 3, 7, 12, dominance=0.35, base_cost=0.07),
    "mating_window": primitive("mating_window", GeneFamily.REPRODUCTION, 2, 5, 10, base_cost=0.03),
    "fecundity": primitive("fecundity", GeneFamily.REPRODUCTION, 3, 8, 14, base_cost=0.09),
    "gestation": primitive("gestation", GeneFamily.REPRODUCTION, 2, 6, 11, base_cost=0.04),
    # TRANSFER
    "hgt": primitive("hgt", GeneFamily.TRANSFER, 2, 6, 11, dominance=0.4, base_cost=0.05),
    "mobile_packet": primitive("mobile_packet", GeneFamily.TRANSFER, 2, 6, 11, dominance=0.35, base_cost=0.06),
    "parasitic_insert": primitive("parasitic_insert", GeneFamily.TRANSFER, 1, 5, 10, dominance=0.3, base_cost=0.07),
    "drive_bias": primitive("drive_bias", GeneFamily.TRANSFER, 2, 6, 11, dominance=0.75, base_cost=0.08),
    # BEHAVIOR
    "approach": primitive("approach", GeneFamily.BEHAVIOR, 2, 6, 10, base_cost=0.03),
    "avoid": primitive("avoid", GeneFamily.BEHAVIOR, 2, 6, 10, base_cost=0.03),
    "graze_behavior": primitive("graze_behavior", GeneFamily.BEHAVIOR, 2, 6, 10, base_cost=0.03),
    "flee": primitive("flee", GeneFamily.BEHAVIOR, 2, 6, 10, base_cost=0.04),
    "bite": primitive("bite", GeneFamily.BEHAVIOR, 2, 6, 10, dominance=0.4, base_cost=0.06),
    "attach": primitive("attach", GeneFamily.BEHAVIOR, 2, 6, 10, base_cost=0.05),
    "school": primitive("school", GeneFamily.BEHAVIOR, 2, 6, 10, dominance=0.4, base_cost=0.04),
    "hide": primitive("hide", GeneFamily.BEHAVIOR, 2, 6, 10, base_cost=0.04),
    "defend": primitive("defend", GeneFamily.BEHAVIOR, 2, 6, 10, base_cost=0.05),
    "mate_seek": primitive("mate_seek", GeneFamily.BEHAVIOR, 2, 6, 10, base_cost=0.04),
    # REGULATION
    "trigger_threshold": primitive("trigger_threshold", GeneFamily.REGULATION, 2, 6, 10, base_cost=0.03),
    "expression_timing": primitive("expression_timing", GeneFamily.REGULATION, 2, 6, 10, base_cost=0.03),
    "dominance": primitive("dominance", GeneFamily.REGULATION, 2, 6, 10, dominance=0.75, base_cost=0.04),
    "suppression": primitive("suppression", GeneFamily.REGULATION, 2, 6, 10, dominance=0.6, base_cost=0.04),
    "developmental_phase": primitive("developmental_phase", GeneFamily.REGULATION, 2, 6, 10, base_cost=0.03),
    # ROBUSTNESS
    "mutation_tolerance": primitive("mutation_tolerance", GeneFamily.ROBUSTNESS, 3, 8, 13, dominance=0.6, base_cost=0.06),
    "repair_accuracy": primitive("repair_accuracy", GeneFamily.ROBUSTNESS, 3, 8, 13, dominance=0.6, base_cost=0.06),
    "immune_resistance": primitive("immune_resistance", GeneFamily.ROBUSTNESS, 2, 6, 11, base_cost=0.05),
    "toxin_tolerance": primitive("toxin_tolerance", GeneFamily.ROBUSTNESS, 3, 8, 13, base_cost=0.05),
    "oxygen_tolerance": primitive("oxygen_tolerance", GeneFamily.ROBUSTNESS, 3, 8, 13, base_cost=0.04),
    "heat_tolerance": primitive("heat_tolerance", GeneFamily.ROBUSTNESS, 3, 8, 13, base_cost=0.05),
    "light_tolerance": primitive("light_tolerance", GeneFamily.ROBUSTNESS, 3, 8, 13, base_cost=0.04),
    "radiation_tolerance": primitive("radiation_tolerance", GeneFamily.ROBUSTNESS, 3, 8, 13, base_cost=0.06),
}

GENE_NAMES: tuple[str, ...] = tuple(PRIMITIVES)

FOUNDER_ARCHETYPES: dict[str, tuple[str, ...]] = {
    "surface_autotroph": (
        "photosynthesis",
        "photosynthesis",
        "photosynthesis",
        "light_tolerance",
        "sense_light",
        "cilia",
        "storage",
        "budding",
        "symmetry",
        "membrane",
        "oxygen_tolerance",
    ),
    "vent_grazer": (
        "chemosynthesis",
        "chemosynthesis",
        "heat_tolerance",
        "sense_heat",
        "sense_chem",
        "grazing",
        "low_o2",
        "membrane",
        "storage",
        "budding",
        "toxin_tolerance",
    ),
    "nimble_grazer": (
        "grazing",
        "graze_behavior",
        "sense_chem",
        "contractility",
        "tail_leverage",
        "appendage",
        "symmetry",
        "turning",
        "movement_efficiency",
        "budding",
        "fecundity",
    ),
    "fragile_predator": (
        "predation",
        "bite",
        "sense_threat",
        "sense_touch",
        "burst",
        "contractility",
        "tail_leverage",
        "appendage",
        "mate_seek",
        "sexual",
        "storage",
    ),
    "armored_scavenger": (
        "scavenging",
        "membrane",
        "membrane",
        "size",
        "defend",
        "sense_chem",
        "low_o2",
        "repair",
        "repair_accuracy",
        "spores",
        "storage",
    ),
}

ESSENTIAL_GENES: frozenset[str] = frozenset(
    {
        "size",
        "membrane",
        "basal_burn",
        "storage",
        "budding",
        "grazing",
        "movement_efficiency",
    }
)
