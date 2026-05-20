from __future__ import annotations

from dataclasses import dataclass
from math import sin
from random import Random
from typing import Iterable


FieldGrid = list[list[float]]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class CellSample:
    depth: float
    temperature: float
    oxygen: float
    ph: float
    turbidity: float
    nutrients: float
    light: float
    current_x: float
    current_y: float
    shelter: float
    substrate: float
    obstacle: float
    food: float
    plankton: float
    waste: float
    toxins: float
    decomposition: float
    population_pressure: float
    reproduction: float
    balance: float

    def resource_score(self) -> float:
        return clamp(self.food * 0.42 + self.plankton * 0.28 + self.nutrients * 0.18 + self.light * 0.10)

    def stress_score(
        self,
        *,
        oxygen_need: float,
        ph_preference: float,
        temperature_preference: float,
        turbidity_tolerance: float,
        toxin_tolerance: float,
    ) -> float:
        hypoxia = max(0.0, oxygen_need - self.oxygen) * 1.15
        ph_stress = abs(self.ph - ph_preference) * 0.88
        temperature_stress = abs(self.temperature - temperature_preference) * 0.72
        turbidity_stress = max(0.0, self.turbidity - turbidity_tolerance) * 0.54
        toxin_stress = max(0.0, self.toxins - toxin_tolerance * 0.82) * 1.08
        crowding = max(0.0, self.population_pressure - 0.55) * 0.36
        return clamp(hypoxia + ph_stress + temperature_stress + turbidity_stress + toxin_stress + crowding)

    def payload(self) -> dict[str, float]:
        return {
            "depth": self.depth,
            "temperature": self.temperature,
            "oxygen": self.oxygen,
            "ph": self.ph,
            "turbidity": self.turbidity,
            "nutrients": self.nutrients,
            "light": self.light,
            "current_x": self.current_x,
            "current_y": self.current_y,
            "shelter": self.shelter,
            "substrate": self.substrate,
            "obstacle": self.obstacle,
            "food": self.food,
            "plankton": self.plankton,
            "waste": self.waste,
            "toxins": self.toxins,
            "decomposition": self.decomposition,
            "population_pressure": self.population_pressure,
            "reproduction": self.reproduction,
            "balance": self.balance,
        }


@dataclass(frozen=True)
class EnvironmentConfig:
    width: int = 96
    height: int = 60
    seed: int = 42
    surface_light: float = 0.95
    nutrient_richness: float = 0.82
    oxygenation: float = 0.74
    toxin_level: float = 0.08
    turbidity: float = 0.28
    temperature_bias: float = 0.0
    ph_bias: float = 0.0
    diffusion_rate: float = 0.070
    regeneration_rate: float = 0.020
    current_strength: float = 0.42
    shelter_density: float = 0.34
    ecology_update_interval: int = 1


class PuddleEnvironment:
    dynamic_fields = (
        "temperature",
        "oxygen",
        "ph",
        "turbidity",
        "nutrients",
        "food",
        "plankton",
        "waste",
        "toxins",
        "decomposition",
        "population_pressure",
        "reproduction",
        "balance",
    )

    render_fields = (
        "depth",
        "temperature",
        "oxygen",
        "ph",
        "turbidity",
        "nutrients",
        "light",
        "shelter",
        "obstacle",
        "food",
        "plankton",
        "waste",
        "toxins",
        "population_pressure",
        "reproduction",
        "balance",
    )

    def __init__(self, config: EnvironmentConfig) -> None:
        self.config = config
        self.rng = Random(config.seed)
        self.width = config.width
        self.height = config.height
        self.tick = 0
        self.fields: dict[str, FieldGrid] = {}
        self.event_signals: list[dict[str, object]] = []
        self.shelter_centers: list[tuple[float, float, float]] = []
        self._generate()

    @property
    def signature(self) -> tuple[float, ...]:
        points = (
            (self.width // 5, self.height // 4),
            (self.width // 2, self.height // 2),
            (self.width * 4 // 5, self.height * 3 // 4),
        )
        values: list[float] = []
        for name in ("depth", "oxygen", "ph", "turbidity", "food", "plankton", "toxins", "shelter", "balance"):
            field = self.fields[name]
            values.extend(round(field[y][x], 4) for x, y in points)
        return tuple(values)

    def randomize(self, seed: int) -> None:
        rng = Random(seed)
        self.config = EnvironmentConfig(
            width=self.width,
            height=self.height,
            seed=seed,
            surface_light=rng.uniform(0.58, 1.12),
            nutrient_richness=rng.uniform(0.34, 1.16),
            oxygenation=rng.uniform(0.38, 0.98),
            toxin_level=rng.uniform(0.02, 0.34),
            turbidity=rng.uniform(0.16, 0.70),
            temperature_bias=rng.uniform(-0.20, 0.18),
            ph_bias=rng.uniform(-0.16, 0.16),
            diffusion_rate=rng.uniform(0.040, 0.120),
            regeneration_rate=rng.uniform(0.012, 0.030),
            current_strength=rng.uniform(0.20, 0.76),
            shelter_density=rng.uniform(0.16, 0.54),
            ecology_update_interval=self.config.ecology_update_interval,
        )
        self.rng = Random(seed)
        self.tick = 0
        self.event_signals = []
        self._generate()

    def _empty_field(self, fill: float = 0.0) -> FieldGrid:
        return [[fill for _ in range(self.width)] for _ in range(self.height)]

    def _generate(self) -> None:
        names = {
            "depth",
            "temperature",
            "oxygen",
            "ph",
            "turbidity",
            "nutrients",
            "light",
            "current_x",
            "current_y",
            "shelter",
            "substrate",
            "obstacle",
            "food",
            "plankton",
            "waste",
            "toxins",
            "decomposition",
            "population_pressure",
            "reproduction",
            "balance",
        }
        self.fields = {name: self._empty_field() for name in names}
        self.shelter_centers = [
            (
                self.rng.uniform(self.width * 0.06, self.width * 0.94),
                self.rng.uniform(self.height * 0.12, self.height * 0.92),
                self.rng.uniform(4.0, 11.0),
            )
            for _ in range(max(3, int(self.config.shelter_density * 12)))
        ]
        basin_x = self.rng.uniform(0.42, 0.60)
        basin_y = self.rng.uniform(0.52, 0.72)
        for y in range(self.height):
            yn = y / max(1, self.height - 1)
            for x in range(self.width):
                xn = x / max(1, self.width - 1)
                radial = 1.0 - min(1.0, ((xn - basin_x) ** 2 / 0.34 + (yn - basin_y) ** 2 / 0.56))
                shelf = 0.25 * (1.0 - yn)
                noise = self.rng.uniform(-0.045, 0.045)
                depth = clamp(0.16 + yn * 0.58 + radial * 0.28 - shelf + noise)
                shelter = self._shelter_value(x, y)
                obstacle = 1.0 if shelter > 0.88 and depth < 0.54 and self.rng.random() < 0.018 else 0.0
                substrate = clamp(0.30 + depth * 0.42 + shelter * 0.18 + self.rng.uniform(-0.06, 0.06))
                turbidity = clamp(self.config.turbidity * (0.52 + depth * 0.44 + substrate * 0.20) + shelter * 0.08)
                light = clamp(self.config.surface_light * (1.0 - depth * 0.72 - turbidity * 0.28) + self.rng.uniform(-0.020, 0.020))
                temperature = clamp(0.42 + self.config.temperature_bias + (1.0 - depth) * 0.18 + light * 0.08 + yn * 0.04)
                nutrients = clamp(self.config.nutrient_richness * (0.25 + depth * 0.38 + substrate * 0.18 + shelter * 0.12))
                oxygen = clamp(self.config.oxygenation * (0.24 + light * 0.48 + (1.0 - turbidity) * 0.20) - depth * 0.10)
                ph = clamp(0.52 + self.config.ph_bias - waste_baseline(depth, substrate) * 0.04 + oxygen * 0.035)
                plankton = clamp((light * 0.46 + nutrients * 0.38) * (1.0 - turbidity * 0.42))
                food = clamp(nutrients * 0.34 + plankton * 0.38 + shelter * 0.12)
                toxins = clamp(self.config.toxin_level * (0.35 + substrate * 0.34 + turbidity * 0.20) + self.rng.uniform(0.0, 0.018))
                current_x, current_y = self._current_value(x, y, basin_x, basin_y)
                self.fields["depth"][y][x] = depth
                self.fields["shelter"][y][x] = shelter
                self.fields["obstacle"][y][x] = obstacle
                self.fields["substrate"][y][x] = substrate
                self.fields["turbidity"][y][x] = turbidity
                self.fields["light"][y][x] = light
                self.fields["temperature"][y][x] = temperature
                self.fields["nutrients"][y][x] = nutrients
                self.fields["oxygen"][y][x] = oxygen
                self.fields["ph"][y][x] = ph
                self.fields["plankton"][y][x] = plankton
                self.fields["food"][y][x] = food
                self.fields["toxins"][y][x] = toxins
                self.fields["waste"][y][x] = waste_baseline(depth, substrate)
                self.fields["decomposition"][y][x] = clamp(substrate * 0.12 + depth * 0.08)
                self.fields["current_x"][y][x] = current_x
                self.fields["current_y"][y][x] = current_y
        self._recompute_reproduction_and_balance()

    def _shelter_value(self, x: int, y: int) -> float:
        value = 0.0
        for cx, cy, radius in self.shelter_centers:
            distance_sq = (x - cx) ** 2 + (y - cy) ** 2
            value += 1.0 / (1.0 + distance_sq / max(1.0, radius * radius))
        return clamp(value * self.config.shelter_density)

    def _current_value(self, x: int, y: int, basin_x: float, basin_y: float) -> tuple[float, float]:
        xn = x / max(1, self.width - 1)
        yn = y / max(1, self.height - 1)
        dx = xn - basin_x
        dy = yn - basin_y
        curl_x = -dy + sin((yn + self.config.seed * 0.001) * 8.0) * 0.12
        curl_y = dx + sin((xn + self.config.seed * 0.001) * 7.0) * 0.10
        return (curl_x * self.config.current_strength * 0.08, curl_y * self.config.current_strength * 0.08)

    def update(self) -> None:
        self.tick += 1
        self.event_signals = []
        interval = max(1, self.config.ecology_update_interval)
        should_update_fields = interval == 1 or self.tick % interval == 0 or self.tick % 25 == 0
        if not should_update_fields:
            for row in self.fields["population_pressure"]:
                for x in range(self.width):
                    row[x] *= 0.93
            return
        if self.tick % 2 == 0:
            for name in self.dynamic_fields:
                self.fields[name] = self._diffuse(self.fields[name], self.config.diffusion_rate)
        seasonal = sin(self.tick / 160.0) * 0.014
        for y in range(self.height):
            for x in range(self.width):
                depth = self.fields["depth"][y][x]
                light = self.fields["light"][y][x]
                substrate = self.fields["substrate"][y][x]
                shelter = self.fields["shelter"][y][x]
                waste = self.fields["waste"][y][x]
                toxins = self.fields["toxins"][y][x]
                nutrients = self.fields["nutrients"][y][x]
                plankton = self.fields["plankton"][y][x]
                decomposition = self.fields["decomposition"][y][x]
                self.fields["temperature"][y][x] = clamp(
                    self.fields["temperature"][y][x] * 0.997 + (0.42 + self.config.temperature_bias + light * 0.10 + seasonal) * 0.003
                )
                self.fields["oxygen"][y][x] = clamp(
                    self.fields["oxygen"][y][x]
                    + self.config.regeneration_rate * (self.config.oxygenation * (0.18 + light * 0.44 + plankton * 0.26))
                    - waste * 0.010
                    - decomposition * 0.004
                )
                self.fields["nutrients"][y][x] = clamp(
                    nutrients
                    + self.config.regeneration_rate * (0.10 + substrate * 0.20 + decomposition * 0.34)
                    - plankton * 0.006
                    - self.fields["food"][y][x] * 0.003
                )
                self.fields["plankton"][y][x] = clamp(
                    plankton + (light * nutrients * 0.016) - self.fields["turbidity"][y][x] * 0.004 - toxins * 0.006
                )
                self.fields["food"][y][x] = clamp(
                    self.fields["food"][y][x] * 0.996
                    + plankton * 0.006
                    + nutrients * (0.003 + shelter * 0.002)
                    + decomposition * 0.002
                )
                self.fields["waste"][y][x] = clamp(waste * 0.990 + self.fields["population_pressure"][y][x] * 0.0015)
                self.fields["decomposition"][y][x] = clamp(decomposition * 0.994 + waste * 0.006 + depth * 0.001)
                self.fields["toxins"][y][x] = clamp(toxins * 0.996 + waste * self.config.toxin_level * 0.002)
                self.fields["turbidity"][y][x] = clamp(
                    self.fields["turbidity"][y][x] * 0.997 + waste * 0.003 + abs(self.fields["current_x"][y][x]) * 0.006
                )
                self.fields["ph"][y][x] = clamp(
                    self.fields["ph"][y][x] * 0.998
                    + (0.52 + self.config.ph_bias + self.fields["oxygen"][y][x] * 0.030 - waste * 0.044) * 0.002
                )
                self.fields["population_pressure"][y][x] *= 0.93
        self._recompute_reproduction_and_balance()
        self._emit_environment_events()

    def _recompute_reproduction_and_balance(self) -> None:
        for y in range(self.height):
            for x in range(self.width):
                oxygen = self.fields["oxygen"][y][x]
                ph = self.fields["ph"][y][x]
                temperature = self.fields["temperature"][y][x]
                toxins = self.fields["toxins"][y][x]
                food = self.fields["food"][y][x]
                plankton = self.fields["plankton"][y][x]
                pressure = self.fields["population_pressure"][y][x]
                resource = clamp(food * 0.40 + plankton * 0.28 + oxygen * 0.20 + self.fields["shelter"][y][x] * 0.08)
                stress = clamp(max(0.0, 0.34 - oxygen) + abs(ph - 0.52) * 0.60 + abs(temperature - 0.50) * 0.42 + toxins * 0.72)
                self.fields["reproduction"][y][x] = clamp(resource - stress - max(0.0, pressure - 0.58) * 0.30)
                self.fields["balance"][y][x] = clamp(resource + self.fields["nutrients"][y][x] * 0.18 - stress - pressure * 0.14)

    def _emit_environment_events(self) -> None:
        if self.tick % 25 != 0:
            return
        averages = self.averages()
        if averages["oxygen"] < 0.22:
            self.event_signals.append({"kind": "oxygen_crash", "value": round(averages["oxygen"], 3)})
        if averages["toxins"] > 0.46:
            self.event_signals.append({"kind": "toxin_bloom", "value": round(averages["toxins"], 3)})
        if averages["food"] < 0.18 and averages["plankton"] < 0.18:
            self.event_signals.append({"kind": "food_collapse", "value": round(max(averages["food"], averages["plankton"]), 3)})
        if averages["balance"] > 0.64:
            self.event_signals.append({"kind": "resource_bloom", "value": round(averages["balance"], 3)})

    def apply_population_pressure(self, positions: Iterable[tuple[float, float, float]]) -> None:
        for x, y, radius in positions:
            ix, iy = self._index(x, y)
            amount = clamp(0.10 + radius * 0.022, 0.0, 0.18)
            for yy in range(max(0, iy - 2), min(self.height, iy + 3)):
                for xx in range(max(0, ix - 2), min(self.width, ix + 3)):
                    distance = abs(xx - ix) + abs(yy - iy)
                    self.fields["population_pressure"][yy][xx] = clamp(
                        self.fields["population_pressure"][yy][xx] + amount / (1.0 + distance)
                    )

    def _diffuse(self, field: FieldGrid, rate: float) -> FieldGrid:
        new = self._empty_field()
        keep = 1.0 - rate
        spread = rate / 4.0
        for y in range(self.height):
            for x in range(self.width):
                total = field[y][x] * keep
                total += field[y][x - 1 if x > 0 else x] * spread
                total += field[y][x + 1 if x < self.width - 1 else x] * spread
                total += field[y - 1 if y > 0 else y][x] * spread
                total += field[y + 1 if y < self.height - 1 else y][x] * spread
                new[y][x] = clamp(total)
        return new

    def sample(self, x: float, y: float) -> CellSample:
        ix, iy = self._index(x, y)
        return CellSample(**{name: self.fields[name][iy][ix] for name in CellSample.__dataclass_fields__})

    def gradient(self, x: float, y: float, field_name: str) -> tuple[float, float]:
        ix, iy = self._index(x, y)
        field = self.fields[field_name]
        left = field[iy][max(0, ix - 1)]
        right = field[iy][min(self.width - 1, ix + 1)]
        up = field[max(0, iy - 1)][ix]
        down = field[min(self.height - 1, iy + 1)][ix]
        return (right - left, down - up)

    def current_at(self, x: float, y: float) -> tuple[float, float]:
        sample = self.sample(x, y)
        return (sample.current_x, sample.current_y)

    def consume(self, field_name: str, x: float, y: float, amount: float) -> float:
        ix, iy = self._index(x, y)
        available = self.fields[field_name][iy][ix]
        taken = min(available, max(0.0, amount))
        self.fields[field_name][iy][ix] = available - taken
        return taken

    def add(self, field_name: str, x: float, y: float, amount: float) -> None:
        ix, iy = self._index(x, y)
        self.fields[field_name][iy][ix] = clamp(self.fields[field_name][iy][ix] + amount)

    def is_obstacle(self, x: float, y: float) -> bool:
        ix, iy = self._index(x, y)
        return self.fields["obstacle"][iy][ix] >= 0.75

    def keep_in_bounds(self, x: float, y: float, vx: float, vy: float) -> tuple[float, float, float, float]:
        if x < 0.6:
            x = 0.6
            vx = abs(vx) * 0.35
        elif x > self.width - 1.6:
            x = self.width - 1.6
            vx = -abs(vx) * 0.35
        if y < 0.6:
            y = 0.6
            vy = abs(vy) * 0.35
        elif y > self.height - 1.6:
            y = self.height - 1.6
            vy = -abs(vy) * 0.35
        if self.is_obstacle(x, y):
            vx = -vx * 0.62
            vy = -vy * 0.62
            x = clamp(x + vx, 0.6, self.width - 1.6)
            y = clamp(y + vy, 0.6, self.height - 1.6)
        return x, y, vx, vy

    def averages(self) -> dict[str, float]:
        total = self.width * self.height
        return {
            name: round(sum(sum(row) for row in self.fields[name]) / max(1, total), 5)
            for name in self.render_fields
            if name in self.fields
        }

    def _index(self, x: float, y: float) -> tuple[int, int]:
        ix = max(0, min(self.width - 1, int(round(x))))
        iy = max(0, min(self.height - 1, int(round(y))))
        return ix, iy

    def _downsampled_fields(self, factor: int = 2) -> dict[str, FieldGrid]:
        view: dict[str, FieldGrid] = {}
        for name in self.render_fields:
            grid = self.fields[name]
            rows: FieldGrid = []
            for y in range(0, self.height, factor):
                row: list[float] = []
                for x in range(0, self.width, factor):
                    values: list[float] = []
                    for yy in range(y, min(self.height, y + factor)):
                        for xx in range(x, min(self.width, x + factor)):
                            values.append(grid[yy][xx])
                    row.append(round(sum(values) / max(1, len(values)), 3))
                rows.append(row)
            view[name] = rows
        return view

    def payload(self) -> dict[str, object]:
        view_fields = self._downsampled_fields(factor=2)
        return {
            "width": self.width,
            "height": self.height,
            "view_width": len(view_fields["depth"][0]) if view_fields["depth"] else self.width,
            "view_height": len(view_fields["depth"]),
            "signature": list(self.signature),
            "fields": view_fields,
            "field_averages": self.averages(),
            "event_signals": list(self.event_signals),
            "shelter_centers": [
                {"x": round(x, 2), "y": round(y, 2), "radius": round(radius, 2)}
                for x, y, radius in self.shelter_centers
            ],
            "config": {
                "surface_light": self.config.surface_light,
                "nutrient_richness": self.config.nutrient_richness,
                "oxygenation": self.config.oxygenation,
                "toxin_level": self.config.toxin_level,
                "turbidity": self.config.turbidity,
                "temperature_bias": self.config.temperature_bias,
                "ph_bias": self.config.ph_bias,
                "diffusion_rate": self.config.diffusion_rate,
                "regeneration_rate": self.config.regeneration_rate,
                "current_strength": self.config.current_strength,
                "shelter_density": self.config.shelter_density,
                "ecology_update_interval": self.config.ecology_update_interval,
            },
        }


def waste_baseline(depth: float, substrate: float) -> float:
    return clamp(0.04 + depth * 0.06 + substrate * 0.035)
