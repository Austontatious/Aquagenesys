from __future__ import annotations

import argparse
import sys
import time

import pygame

from dirty_puddle.sim.world import World, load_world_config
from dirty_puddle.ui.controls import (
    ControlState,
    RUNTIME_SLIDERS,
    adjust_mutation,
    adjust_nutrients,
    adjust_volatility,
    runtime_value,
    set_runtime_value,
)
from dirty_puddle.ui.panels import StatsPanel


PANEL_WIDTH = 360
FPS = 60
FIELD_NUTRIENT = "nutrient"
FIELD_HEAT = "heat"
FIELD_TOXIN = "toxin"


def run_app(config_name: str = "default_live") -> int:
    pygame.init()
    config = load_world_config(config_name)
    world = World(config)
    controls = ControlState()
    field_mode = FIELD_NUTRIENT
    cell_size = _cell_size_for(world.config.width, world.config.height)
    sim_width = world.config.width * cell_size
    sim_height = world.config.height * cell_size
    screen = pygame.display.set_mode((sim_width + PANEL_WIDTH, sim_height))
    pygame.display.set_caption("Aquagenesys / Dirty Puddle")
    clock = pygame.time.Clock()
    panel = StatsPanel(PANEL_WIDTH, sim_height)
    slider_rects: dict[str, pygame.Rect] = {}
    active_slider: str | None = None

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for key, rect in slider_rects.items():
                    if rect.collidepoint(event.pos):
                        active_slider = key
                        _set_slider_from_mouse(event.pos[0], rect, key, world, controls)
                        break
            elif event.type == pygame.MOUSEMOTION and active_slider is not None:
                rect = slider_rects.get(active_slider)
                if rect is not None:
                    _set_slider_from_mouse(event.pos[0], rect, active_slider, world, controls)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                active_slider = None
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    controls.toggle_pause()
                elif event.key == pygame.K_RIGHT:
                    controls.faster()
                elif event.key == pygame.K_LEFT:
                    controls.slower()
                elif event.key == pygame.K_r:
                    world.reset(config)
                elif event.key == pygame.K_LEFTBRACKET:
                    adjust_mutation(world, -0.005)
                elif event.key == pygame.K_RIGHTBRACKET:
                    adjust_mutation(world, 0.005)
                elif event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE):
                    adjust_nutrients(world, -0.05)
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS):
                    adjust_nutrients(world, 0.05)
                elif event.key == pygame.K_COMMA:
                    adjust_volatility(world, -0.03)
                elif event.key == pygame.K_PERIOD:
                    adjust_volatility(world, 0.03)
                elif event.key == pygame.K_1:
                    field_mode = FIELD_NUTRIENT
                elif event.key == pygame.K_2:
                    field_mode = FIELD_HEAT
                elif event.key == pygame.K_3:
                    field_mode = FIELD_TOXIN

        if not controls.paused:
            world.step(controls.speed)

        render_start = time.perf_counter()
        _draw_world(screen, world, field_mode, cell_size)
        slider_values = {
            spec.key: runtime_value(world, controls, spec.key)
            for spec in RUNTIME_SLIDERS
        }
        slider_rects = panel.draw(
            screen,
            rect=pygame.Rect(sim_width, 0, PANEL_WIDTH, sim_height),
            snapshot=world.metrics.latest(),
            history=world.metrics,
            lineages=world.lineages,
            speed=controls.speed,
            paused=controls.paused,
            mutation_rate=world.config.mutation_rate,
            nutrient_abundance=world.config.nutrient_abundance,
            volatility=world.config.volatility,
            performance=world.performance.snapshot(),
            slider_specs=RUNTIME_SLIDERS,
            slider_values=slider_values,
        )
        _draw_mode_badge(screen, field_mode)
        pygame.display.flip()
        world.record_render_cost(time.perf_counter() - render_start)
        clock.tick(FPS)

    pygame.quit()
    return 0


def _cell_size_for(width: int, height: int) -> int:
    return max(4, min(10, 1024 // max(1, width), 720 // max(1, height)))


def _draw_world(
    screen: pygame.Surface,
    world: World,
    field_mode: str,
    cell_size: int,
) -> None:
    screen.fill((8, 11, 14))
    for y in range(world.config.height):
        for x in range(world.config.width):
            if field_mode == FIELD_HEAT:
                heat = world.fields.heat[y][x]
                color = (int(54 + heat * 150), int(26 + heat * 64), 34)
            elif field_mode == FIELD_TOXIN:
                toxin = world.fields.toxin[y][x]
                color = (34, int(42 + toxin * 118), int(56 + toxin * 134))
            else:
                nutrient = world.fields.nutrient[y][x]
                color = (int(10 + nutrient * 36), int(24 + nutrient * 90), 32)
            pygame.draw.rect(
                screen,
                color,
                pygame.Rect(x * cell_size, y * cell_size, cell_size, cell_size),
            )

    _draw_colonies(screen, world, cell_size)
    _draw_organisms(screen, world, cell_size)
    _draw_aquatics(screen, world, cell_size)
    for cell in world.cells:
        color = cell.genome.color()
        rect = pygame.Rect(
            cell.x * cell_size + 1,
            cell.y * cell_size + 1,
            max(2, cell_size - 2),
            max(2, cell_size - 2),
        )
        pygame.draw.rect(screen, color, rect)


def _draw_colonies(screen: pygame.Surface, world: World, cell_size: int) -> None:
    for colony in world.colonies.active.values():
        record = world.lineages.records.get(colony.dominant_lineage)
        color = record.color if record else (220, 220, 220)
        center = (
            int((colony.centroid[0] + 0.5) * cell_size),
            int((colony.centroid[1] + 0.5) * cell_size),
        )
        radius = max(cell_size * 2, int((colony.size ** 0.5) * cell_size * 0.9))
        pygame.draw.circle(screen, color, center, radius, 2)


def _draw_organisms(screen: pygame.Surface, world: World, cell_size: int) -> None:
    for organism in world.organisms:
        record = world.lineages.records.get(organism.origin_lineage_id)
        color = record.color if record else (230, 230, 230)
        center = (
            int((organism.x + 0.5) * cell_size),
            int((organism.y + 0.5) * cell_size),
        )
        radius = max(cell_size, int((organism.body_size ** 0.5) * cell_size * 0.55))
        pygame.draw.circle(screen, (12, 15, 18), center, radius + 2)
        pygame.draw.circle(screen, color, center, radius)
        pygame.draw.circle(screen, (238, 244, 248), center, radius, 1)


def _draw_aquatics(screen: pygame.Surface, world: World, cell_size: int) -> None:
    for aquatic in world.aquatics:
        center = (
            int((aquatic.x + 0.5) * cell_size),
            int((aquatic.y + 0.5) * cell_size),
        )
        radius = max(cell_size + 1, int((aquatic.body_size ** 0.5) * cell_size * 0.70))
        color = aquatic.color_marker
        nose = (
            int(center[0] + aquatic.vx * cell_size * 1.4),
            int(center[1] + aquatic.vy * cell_size * 1.4),
        )
        pygame.draw.circle(screen, (4, 7, 10), center, radius + 3)
        pygame.draw.circle(screen, color, center, radius)
        pygame.draw.line(screen, (245, 249, 252), center, nose, 2)
        pygame.draw.circle(screen, (245, 249, 252), center, radius, 1)


def _set_slider_from_mouse(
    mouse_x: int,
    rect: pygame.Rect,
    key: str,
    world: World,
    controls: ControlState,
) -> None:
    spec = next(item for item in RUNTIME_SLIDERS if item.key == key)
    ratio = (mouse_x - rect.x) / max(1, rect.width)
    ratio = max(0.0, min(1.0, ratio))
    value = spec.minimum + ratio * (spec.maximum - spec.minimum)
    if spec.step > 0:
        value = round(value / spec.step) * spec.step
    set_runtime_value(world, controls, key, value)


def _draw_mode_badge(screen: pygame.Surface, field_mode: str) -> None:
    font = pygame.font.Font(None, 20)
    label = {"nutrient": "1 Nutrient", "heat": "2 Heat", "toxin": "3 Toxin"}[field_mode]
    image = font.render(label, True, (226, 231, 235))
    rect = image.get_rect(topleft=(10, 8)).inflate(14, 8)
    pygame.draw.rect(screen, (18, 22, 26), rect)
    pygame.draw.rect(screen, (65, 73, 82), rect, 1)
    screen.blit(image, (rect.x + 7, rect.y + 4))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Dirty Puddle pygame simulator")
    parser.add_argument("--config", default="default_live", help="config name or path")
    args = parser.parse_args(argv)
    return run_app(args.config)


if __name__ == "__main__":
    sys.exit(main())
