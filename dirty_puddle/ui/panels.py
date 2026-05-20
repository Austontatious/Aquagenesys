from __future__ import annotations

import pygame

from dirty_puddle.sim.lineage import LineageTracker
from dirty_puddle.sim.metrics import MetricsHistory, PerformanceSnapshot, WorldSnapshot
from dirty_puddle.ui.controls import SliderSpec


Color = tuple[int, int, int]

PANEL_BG = (24, 28, 33)
PANEL_EDGE = (52, 60, 68)
TEXT = (226, 231, 235)
MUTED = (142, 153, 162)
GRID = (70, 77, 84)
POP_LINE = (245, 210, 86)


class StatsPanel:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.font = pygame.font.Font(None, 22)
        self.small = pygame.font.Font(None, 18)

    def draw(
        self,
        surface: pygame.Surface,
        *,
        rect: pygame.Rect,
        snapshot: WorldSnapshot | None,
        history: MetricsHistory,
        lineages: LineageTracker,
        speed: int,
        paused: bool,
        mutation_rate: float,
        nutrient_abundance: float,
        volatility: float,
        performance: PerformanceSnapshot,
        slider_specs: tuple[SliderSpec, ...],
        slider_values: dict[str, float],
    ) -> dict[str, pygame.Rect]:
        pygame.draw.rect(surface, PANEL_BG, rect)
        pygame.draw.line(surface, PANEL_EDGE, rect.topleft, rect.bottomleft, 1)
        slider_rects: dict[str, pygame.Rect] = {}
        x = rect.x + 16
        y = rect.y + 14
        title = "Paused" if paused else "Running"
        self._line(surface, f"{title}  x{speed}", x, y, TEXT, self.font)
        y += 28
        if snapshot:
            self._line(surface, f"Tick {snapshot.tick}", x, y, TEXT)
            y += 22
            self._line(
                surface,
                f"Stage {snapshot.environment_stage.replace('_', ' ')}",
                x,
                y,
                TEXT,
            )
            y += 22
            self._line(surface, f"Population {snapshot.population}", x, y, TEXT)
            y += 22
            self._line(
                surface,
                f"Org {snapshot.organism_count}  Aqua {snapshot.aquatic_count}  Support {snapshot.environment_support_score:.2f}",
                x,
                y,
                TEXT,
            )
            y += 22
            self._line(surface, f"Births {snapshot.births}  Deaths {snapshot.deaths}", x, y, TEXT)
            y += 22
            self._line(surface, f"Energy {snapshot.mean_energy:.2f}  Age {snapshot.mean_age:.0f}", x, y, TEXT)
            y += 22
            self._line(
                surface,
                f"Colonies {snapshot.colony_count}  Adhesion {snapshot.mean_adhesion:.2f}",
                x,
                y,
                TEXT,
            )
            y += 22
            self._line(
                surface,
                f"Coop {snapshot.mean_cooperation:.2f}  Cheat {snapshot.mean_selfishness:.2f}",
                x,
                y,
                TEXT,
            )
            y += 20
            self._line(surface, f"Eff mut {snapshot.effective_mutation_rate:.3f}", x, y, TEXT)
            y += 20
            aquatic = snapshot.aquatic_metrics
            self._line(
                surface,
                f"Aqua speed {float(aquatic.get('average_speed', 0.0)):.2f}  pred {int(aquatic.get('predation_events', 0))}",
                x,
                y,
                TEXT,
            )
            y += 20
        self._line(surface, "Space pause  R reset  1/2/3 fields", x, y, MUTED)
        y += 18
        self._line(surface, "Drag sliders or use arrow/[ ]/-/=/,/. keys", x, y, MUTED)
        y += 22
        self._line(surface, f"Ticks/s {performance.ticks_per_sec:,.0f}", x, y, TEXT)
        y += 20
        self._line(surface, f"Cells/s {performance.cells_per_sec:,.0f}", x, y, TEXT)
        y += 20
        self._line(surface, f"Avg pop {performance.avg_population:.0f}  Max {performance.max_population}", x, y, TEXT)
        y += 20
        self._line(
            surface,
            f"Field {performance.field_update_cost_ms:.2f}ms  Agents {performance.agent_update_cost_ms:.2f}ms",
            x,
            y,
            MUTED,
        )
        y += 20
        self._line(
            surface,
            f"Render {performance.render_cost_ms:.2f}ms  Metrics {performance.metrics_sample_cost_ms:.2f}ms",
            x,
            y,
            MUTED,
        )
        y += 22

        slider_rects.update(
            self._draw_sliders(
                surface,
                x=x,
                y=y,
                width=rect.width - 32,
                slider_specs=slider_specs,
                slider_values=slider_values,
            )
        )
        y += len(slider_specs) * 16 + 12

        remaining = max(96, rect.bottom - y - 20)
        chart_height = max(64, min(108, remaining // 2))
        chart_rect = pygame.Rect(rect.x + 14, y, rect.width - 28, chart_height)
        self._draw_population_chart(surface, chart_rect, history)
        lineage_y = chart_rect.bottom + 16
        lineage_rect = pygame.Rect(
            rect.x + 14,
            lineage_y,
            rect.width - 28,
            max(44, rect.bottom - lineage_y - 14),
        )
        self._draw_lineages(surface, lineage_rect, snapshot, lineages)
        return slider_rects

    def _line(
        self,
        surface: pygame.Surface,
        text: str,
        x: int,
        y: int,
        color: Color,
        font: pygame.font.Font | None = None,
    ) -> None:
        image = (font or self.small).render(text, True, color)
        surface.blit(image, (x, y))

    def _draw_population_chart(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        history: MetricsHistory,
    ) -> None:
        pygame.draw.rect(surface, (16, 19, 23), rect)
        pygame.draw.rect(surface, PANEL_EDGE, rect, 1)
        pops = history.populations()
        if len(pops) < 2:
            return
        max_pop = max(max(pops), 1)
        points: list[tuple[int, int]] = []
        for index, pop in enumerate(pops):
            x = rect.x + int(index * (rect.width - 1) / max(1, len(pops) - 1))
            y = rect.bottom - 3 - int(pop * (rect.height - 8) / max_pop)
            points.append((x, y))
        if len(points) >= 2:
            pygame.draw.lines(surface, POP_LINE, False, points, 2)
        for i in range(1, 4):
            gy = rect.y + int(rect.height * i / 4)
            pygame.draw.line(surface, GRID, (rect.x, gy), (rect.right, gy), 1)

    def _draw_lineages(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        snapshot: WorldSnapshot | None,
        lineages: LineageTracker,
    ) -> None:
        pygame.draw.rect(surface, (16, 19, 23), rect)
        pygame.draw.rect(surface, PANEL_EDGE, rect, 1)
        self._line(surface, "Lineages", rect.x + 8, rect.y + 8, TEXT)
        if not snapshot:
            return
        y = rect.y + 34
        total = max(1, snapshot.population)
        for lineage_id, count in sorted(snapshot.lineage_counts.items(), key=lambda item: item[1], reverse=True)[:8]:
            record = lineages.records.get(lineage_id)
            color = record.color if record else (180, 180, 180)
            pygame.draw.rect(surface, color, pygame.Rect(rect.x + 8, y + 3, 10, 10))
            label = f"L{lineage_id} {count}  {count / total:0.0%}"
            self._line(surface, label, rect.x + 24, y, TEXT)
            bar_width = int((rect.width - 116) * count / total)
            pygame.draw.rect(surface, color, pygame.Rect(rect.right - 76, y + 3, max(2, bar_width), 8))
            y += 20
            if y > rect.bottom - 20:
                break

    def _draw_sliders(
        self,
        surface: pygame.Surface,
        *,
        x: int,
        y: int,
        width: int,
        slider_specs: tuple[SliderSpec, ...],
        slider_values: dict[str, float],
    ) -> dict[str, pygame.Rect]:
        rects: dict[str, pygame.Rect] = {}
        label_width = 88
        track_width = max(80, width - label_width - 50)
        for index, spec in enumerate(slider_specs):
            row_y = y + index * 16
            value = slider_values.get(spec.key, spec.minimum)
            self._line(surface, spec.label, x, row_y - 1, MUTED, self.small)
            track = pygame.Rect(x + label_width, row_y + 5, track_width, 4)
            pygame.draw.rect(surface, GRID, track)
            ratio = (value - spec.minimum) / max(0.000001, spec.maximum - spec.minimum)
            ratio = max(0.0, min(1.0, ratio))
            knob_x = track.x + int(track.width * ratio)
            pygame.draw.circle(surface, TEXT, (knob_x, track.centery), 5)
            rects[spec.key] = track.inflate(8, 10)
            value_text = f"{value:.3f}" if spec.step < 0.01 else f"{value:.2f}"
            if spec.step >= 1.0:
                value_text = str(int(round(value)))
            self._line(surface, value_text, track.right + 8, row_y - 1, TEXT, self.small)
        return rects
