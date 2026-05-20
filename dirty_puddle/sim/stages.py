from __future__ import annotations

from enum import Enum


class CellStage(str, Enum):
    NEWBORN = "newborn"
    ADULT = "adult"
    SENESCENT = "senescent"


class EnvironmentStage(str, Enum):
    DIRTY_PUDDLE = "dirty_puddle"
    COLONY_POND = "colony_pond"
    MULTICELLULAR_POND = "multicellular_pond"
    AQUATIC_ECOSYSTEM = "aquatic_ecosystem"
    FISH_TANK_PLACEHOLDER = "fish_tank_placeholder"


def stage_for(age: int, max_age: int) -> CellStage:
    if age < 25:
        return CellStage.NEWBORN
    if age > max_age * 0.78:
        return CellStage.SENESCENT
    return CellStage.ADULT
