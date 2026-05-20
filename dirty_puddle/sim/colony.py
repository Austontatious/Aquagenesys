from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import math

from dirty_puddle.sim.agents import Cell
from dirty_puddle.sim.genome import average_genome_traits


@dataclass(frozen=True)
class Colony:
    colony_id: int
    size: int
    dominant_lineage: int
    lineage_mix: dict[int, int]
    average_traits: dict[str, float]
    age: int
    centroid: tuple[float, float]
    cooperation_rate: float
    cheater_rate: float
    member_ids: tuple[int, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ColonyTracker:
    def __init__(self) -> None:
        self.active: dict[int, Colony] = {}
        self._members_by_colony: dict[int, set[int]] = {}
        self._next_colony_id = 1

    def update(
        self,
        *,
        cells: list[Cell],
        cell_by_index: dict[int, Cell],
        index_by_cell_id: dict[int, int],
        neighbor_indices: list[tuple[int, ...]],
        tick: int,
        adhesion_threshold: float,
        compatibility_threshold: float,
        min_size: int,
    ) -> dict[int, Colony]:
        for cell in cells:
            cell.colony_id = None

        visited: set[int] = set()
        components: list[list[Cell]] = []
        for cell in cells:
            if cell.id in visited or self._effective_adhesion(cell) < adhesion_threshold:
                continue
            component = self._collect_component(
                cell,
                visited,
                cell_by_index,
                index_by_cell_id,
                neighbor_indices,
                adhesion_threshold,
                compatibility_threshold,
            )
            if len(component) >= min_size:
                components.append(component)

        next_active: dict[int, Colony] = {}
        next_members: dict[int, set[int]] = {}
        used_previous: set[int] = set()
        for component in components:
            member_ids = {cell.id for cell in component}
            colony_id, age = self._stable_identity(member_ids, used_previous)
            colony = self._make_colony(colony_id, age, component)
            next_active[colony_id] = colony
            next_members[colony_id] = member_ids
            for cell in component:
                cell.colony_id = colony_id

        self.active = next_active
        self._members_by_colony = next_members
        return self.active

    def _collect_component(
        self,
        start: Cell,
        visited: set[int],
        cell_by_index: dict[int, Cell],
        index_by_cell_id: dict[int, int],
        neighbor_indices: list[tuple[int, ...]],
        adhesion_threshold: float,
        compatibility_threshold: float,
    ) -> list[Cell]:
        stack = [start]
        component: list[Cell] = []
        visited.add(start.id)
        while stack:
            cell = stack.pop()
            component.append(cell)
            index = index_by_cell_id[cell.id]
            for neighbor_index in neighbor_indices[index]:
                other = cell_by_index.get(neighbor_index)
                if other is None or other.id in visited:
                    continue
                if self._can_adhere(cell, other, adhesion_threshold, compatibility_threshold):
                    visited.add(other.id)
                    stack.append(other)
        return component

    def _can_adhere(
        self,
        a: Cell,
        b: Cell,
        adhesion_threshold: float,
        compatibility_threshold: float,
    ) -> bool:
        if self._effective_adhesion(a) < adhesion_threshold:
            return False
        if self._effective_adhesion(b) < adhesion_threshold:
            return False
        related = a.lineage_id == b.lineage_id or a.genome.distance(b.genome) <= compatibility_threshold
        if not related:
            return False
        adhesion_gap = abs(a.genome.adhesion - b.genome.adhesion)
        return adhesion_gap <= 0.55

    def _effective_adhesion(self, cell: Cell) -> float:
        return cell.genome.adhesion * (1.0 - cell.genome.selfishness * 0.35)

    def _stable_identity(self, member_ids: set[int], used_previous: set[int]) -> tuple[int, int]:
        best_colony_id: int | None = None
        best_overlap = 0
        for colony_id, previous_members in self._members_by_colony.items():
            if colony_id in used_previous:
                continue
            overlap = len(member_ids & previous_members)
            if overlap > best_overlap:
                best_colony_id = colony_id
                best_overlap = overlap
        if best_colony_id is not None and best_overlap > 0:
            used_previous.add(best_colony_id)
            previous = self.active[best_colony_id]
            return best_colony_id, previous.age + 1
        colony_id = self._next_colony_id
        self._next_colony_id += 1
        return colony_id, 1

    def _make_colony(self, colony_id: int, age: int, members: list[Cell]) -> Colony:
        lineage_mix = dict(Counter(cell.lineage_id for cell in members))
        dominant_lineage = max(lineage_mix.items(), key=lambda item: (item[1], -item[0]))[0]
        size = len(members)
        cooperation_rate = math.fsum(cell.genome.cooperation for cell in members) / size
        cheater_rate = math.fsum(cell.genome.selfishness for cell in members) / size
        centroid = (
            math.fsum(cell.x for cell in members) / size,
            math.fsum(cell.y for cell in members) / size,
        )
        return Colony(
            colony_id=colony_id,
            size=size,
            dominant_lineage=dominant_lineage,
            lineage_mix=lineage_mix,
            average_traits=average_genome_traits(members),
            age=age,
            centroid=centroid,
            cooperation_rate=cooperation_rate,
            cheater_rate=cheater_rate,
            member_ids=tuple(sorted(cell.id for cell in members)),
        )

    def size_distribution(self) -> list[int]:
        return sorted((colony.size for colony in self.active.values()), reverse=True)

    def dominant_colony_lineage(self) -> int | None:
        if not self.active:
            return None
        largest = max(self.active.values(), key=lambda colony: (colony.size, -colony.colony_id))
        return largest.dominant_lineage
