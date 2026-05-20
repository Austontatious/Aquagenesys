from __future__ import annotations

from dataclasses import dataclass
import math
import random

from dirty_puddle.sim.genome import clamp


Grid = list[list[float]]


def make_grid(width: int, height: int, value: float = 0.0) -> Grid:
    return [[value for _ in range(width)] for _ in range(height)]


@dataclass(slots=True)
class FieldSample:
    nutrient: float
    heat: float
    toxin: float


class EnvironmentalFields:
    def __init__(
        self,
        width: int,
        height: int,
        *,
        nutrient_abundance: float,
        rng: random.Random,
    ) -> None:
        self.width = width
        self.height = height
        self._heat_shift = 0.0
        self._toxin_shift = 0.0
        self.source = make_grid(width, height)
        self.nutrient = make_grid(width, height)
        self.base_heat = make_grid(width, height)
        self.base_toxin = make_grid(width, height)
        self.heat = make_grid(width, height)
        self.toxin = make_grid(width, height)
        self._build_base_fields(nutrient_abundance, rng)

    def _build_base_fields(self, nutrient_abundance: float, rng: random.Random) -> None:
        for y in range(self.height):
            yf = y / max(1, self.height - 1)
            for x in range(self.width):
                xf = x / max(1, self.width - 1)
                wave = 0.5 + 0.5 * math.sin(xf * math.tau * 2.5 + yf * math.tau)
                speckle = rng.random() * 0.16
                if x < self.width * 0.34:
                    heat = 0.16 + 0.09 * wave
                    toxin = 0.20 + 0.08 * (1.0 - wave)
                    source = 0.66 + speckle
                elif x > self.width * 0.66:
                    heat = 0.78 + 0.14 * wave
                    toxin = 0.22 + 0.07 * (1.0 - wave)
                    source = 0.60 + speckle
                else:
                    heat = 0.32 + 0.11 * wave
                    toxin = 0.76 + 0.16 * (1.0 - wave)
                    source = 0.62 + speckle

                edge = min(xf, 1.0 - xf, yf, 1.0 - yf)
                edge_penalty = 0.16 if edge < 0.08 else 0.0
                self.source[y][x] = clamp(source - edge_penalty, 0.0, 1.2)
                self.nutrient[y][x] = (
                    clamp(nutrient_abundance * self.source[y][x], 0.0, 2.4)
                    * (0.72 + rng.random() * 0.22)
                )
                self.base_heat[y][x] = clamp(heat, 0.0, 1.0)
                self.base_toxin[y][x] = clamp(toxin, 0.0, 1.0)
                self.heat[y][x] = self.base_heat[y][x]
                self.toxin[y][x] = self.base_toxin[y][x]

    def set_nutrient_abundance(self, abundance: float) -> None:
        abundance = clamp(abundance, 0.0, 3.0)
        for y in range(self.height):
            for x in range(self.width):
                base = self.source[y][x]
                if base > 0:
                    normalized = clamp(base, 0.0, 1.2)
                    self.source[y][x] = clamp(abundance * normalized, 0.0, 2.4)

    def sample(self, x: int, y: int) -> FieldSample:
        return FieldSample(
            nutrient=self.nutrient[y][x],
            heat=self.heat[y][x],
            toxin=self.toxin[y][x],
        )

    def consume(self, x: int, y: int, amount: float) -> float:
        current = self.nutrient[y][x]
        if amount <= 0.0:
            return 0.0
        eaten = current if current < amount else amount
        self.nutrient[y][x] = current - eaten
        return eaten

    def tick(
        self,
        *,
        nutrient_regen_rate: float,
        volatility: float,
        nutrient_abundance: float,
        rng: random.Random,
    ) -> None:
        heat_shift = self._heat_shift * 0.985 + rng.gauss(0.0, volatility * 0.004)
        if heat_shift < -0.12:
            heat_shift = -0.12
        elif heat_shift > 0.12:
            heat_shift = 0.12
        toxin_shift = self._toxin_shift * 0.985 + rng.gauss(0.0, volatility * 0.004)
        if toxin_shift < -0.12:
            toxin_shift = -0.12
        elif toxin_shift > 0.12:
            toxin_shift = 0.12
        self._heat_shift = heat_shift
        self._toxin_shift = toxin_shift
        abundance = nutrient_abundance
        if abundance < 0.0:
            abundance = 0.0
        elif abundance > 3.0:
            abundance = 3.0
        regen = nutrient_regen_rate
        for y in range(self.height):
            source_row = self.source[y]
            nutrient_row = self.nutrient[y]
            heat_row = self.heat[y]
            toxin_row = self.toxin[y]
            base_heat_row = self.base_heat[y]
            base_toxin_row = self.base_toxin[y]
            for x in range(self.width):
                target_nutrient = source_row[x] * abundance
                if target_nutrient > 2.4:
                    target_nutrient = 2.4
                nutrient = nutrient_row[x] + (target_nutrient - nutrient_row[x]) * regen
                if nutrient < 0.0:
                    nutrient = 0.0
                elif nutrient > 2.4:
                    nutrient = 2.4
                nutrient_row[x] = nutrient

                heat = heat_row[x] + (base_heat_row[x] + heat_shift - heat_row[x]) * 0.055
                if heat < 0.0:
                    heat = 0.0
                elif heat > 1.0:
                    heat = 1.0
                heat_row[x] = heat

                toxin = toxin_row[x] + (base_toxin_row[x] + toxin_shift - toxin_row[x]) * 0.055
                if toxin < 0.0:
                    toxin = 0.0
                elif toxin > 1.0:
                    toxin = 1.0
                toxin_row[x] = toxin

    def averages(self) -> tuple[float, float, float]:
        total = self.width * self.height
        nutrient = 0.0
        heat = 0.0
        toxin = 0.0
        for y in range(self.height):
            nutrient += math.fsum(self.nutrient[y])
            heat += math.fsum(self.heat[y])
            toxin += math.fsum(self.toxin[y])
        return nutrient / total, heat / total, toxin / total
