from __future__ import annotations

from dataclasses import dataclass

from dirty_puddle.sim.genome import clamp
from dirty_puddle.sim.world import World


@dataclass
class ControlState:
    paused: bool = False
    speed: int = 1
    max_speed: int = 64

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def faster(self) -> None:
        self.speed = min(self.max_speed, self.speed * 2)

    def slower(self) -> None:
        self.speed = max(1, self.speed // 2)


@dataclass(frozen=True)
class SliderSpec:
    key: str
    label: str
    minimum: float
    maximum: float
    step: float


RUNTIME_SLIDERS: tuple[SliderSpec, ...] = (
    SliderSpec("speed", "speed", 1.0, 64.0, 1.0),
    SliderSpec("mutation_rate", "mutation", 0.0, 0.25, 0.005),
    SliderSpec("nutrient_abundance", "nutrients", 0.0, 3.0, 0.05),
    SliderSpec("volatility", "volatility", 0.0, 1.5, 0.03),
    SliderSpec("radiation_level", "radiation", 0.0, 2.0, 0.02),
    SliderSpec("ph_drift", "pH drift", -1.0, 1.0, 0.02),
    SliderSpec("salinity_drift", "salinity", -1.0, 1.0, 0.02),
    SliderSpec("temperature_drift", "temp drift", -1.0, 1.0, 0.02),
    SliderSpec("mineral_richness", "minerals", 0.0, 3.0, 0.05),
    SliderSpec("predation_pressure", "predation", 0.0, 3.0, 0.05),
    SliderSpec("reproduction_cost", "repro cost", 0.25, 3.0, 0.05),
    SliderSpec("energy_decay", "metabolism", 0.25, 3.0, 0.05),
    SliderSpec("random_catastrophe_frequency", "catastrophe", 0.0, 0.02, 0.0005),
    SliderSpec("cooperation_cost", "coop cost", 0.0, 0.25, 0.005),
    SliderSpec("cooperation_benefit_radius", "coop radius", 1.0, 4.0, 1.0),
    SliderSpec("adhesion_cost", "adhesion cost", 0.0, 0.25, 0.005),
    SliderSpec("colony_stress_protection", "protection", 0.0, 0.9, 0.02),
    SliderSpec("cheater_advantage", "cheater adv", 0.0, 3.0, 0.05),
    SliderSpec("stage4_min_support", "aqua support", 0.0, 1.0, 0.02),
    SliderSpec("aquatic_reproduction_threshold", "aqua repro", 10.0, 220.0, 2.0),
    SliderSpec("aquatic_reproduction_cost", "aqua cost", 0.1, 0.9, 0.02),
    SliderSpec("aquatic_degrade_support_threshold", "aqua collapse", 0.0, 1.0, 0.02),
)


def runtime_value(world: World, controls: ControlState, key: str) -> float:
    if key == "speed":
        return float(controls.speed)
    return float(getattr(world.config, key))


def set_runtime_value(world: World, controls: ControlState, key: str, value: float) -> None:
    spec = next(item for item in RUNTIME_SLIDERS if item.key == key)
    value = clamp(value, spec.minimum, spec.maximum)
    if spec.step >= 1.0:
        value = round(value / spec.step) * spec.step
    if key == "speed":
        controls.speed = max(1, min(controls.max_speed, int(round(value))))
        return
    if key == "cooperation_benefit_radius":
        world.update_controls(**{key: int(round(value))})
    else:
        world.update_controls(**{key: value})


def adjust_mutation(world: World, delta: float) -> None:
    world.update_controls(
        mutation_rate=clamp(world.config.mutation_rate + delta, 0.0, 1.0)
    )


def adjust_nutrients(world: World, delta: float) -> None:
    world.update_controls(
        nutrient_abundance=clamp(world.config.nutrient_abundance + delta, 0.0, 3.0)
    )


def adjust_volatility(world: World, delta: float) -> None:
    world.update_controls(volatility=clamp(world.config.volatility + delta, 0.0, 1.5))
