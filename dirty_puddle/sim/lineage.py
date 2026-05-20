from __future__ import annotations

from dataclasses import dataclass, field

from dirty_puddle.sim.genome import Genome


@dataclass
class LineageRecord:
    lineage_id: int
    founder_id: int
    parent_lineage_id: int | None
    birth_tick: int
    founder_genome: dict[str, float]
    color: tuple[int, int, int]
    births: int = 0
    deaths: int = 0
    alive: int = 0
    last_seen_tick: int = 0
    children: list[int] = field(default_factory=list)

    def founder_genome_to_genome(self) -> Genome:
        return Genome(**self.founder_genome)


class LineageTracker:
    def __init__(self) -> None:
        self.records: dict[int, LineageRecord] = {}
        self._next_lineage_id = 1
        self.extinction_events = 0
        self.speciation_events = 0
        self._extinct_lineages: set[int] = set()

    def create_founder(self, *, founder_id: int, genome: Genome, tick: int) -> int:
        lineage_id = self._next_lineage_id
        self._next_lineage_id += 1
        self.records[lineage_id] = LineageRecord(
            lineage_id=lineage_id,
            founder_id=founder_id,
            parent_lineage_id=None,
            birth_tick=tick,
            founder_genome=genome.signature(),
            color=genome.color(),
            births=1,
            alive=1,
            last_seen_tick=tick,
        )
        return lineage_id

    def create_split(
        self,
        *,
        founder_id: int,
        parent_lineage_id: int,
        genome: Genome,
        tick: int,
    ) -> int:
        lineage_id = self._next_lineage_id
        self._next_lineage_id += 1
        self.records[lineage_id] = LineageRecord(
            lineage_id=lineage_id,
            founder_id=founder_id,
            parent_lineage_id=parent_lineage_id,
            birth_tick=tick,
            founder_genome=genome.signature(),
            color=genome.color(),
            births=1,
            alive=1,
            last_seen_tick=tick,
        )
        self.records[parent_lineage_id].children.append(lineage_id)
        self.speciation_events += 1
        return lineage_id

    def record_birth(self, lineage_id: int, tick: int) -> None:
        record = self.records[lineage_id]
        record.births += 1
        record.alive += 1
        record.last_seen_tick = tick
        self._extinct_lineages.discard(lineage_id)

    def record_death(self, lineage_id: int, tick: int) -> None:
        record = self.records[lineage_id]
        record.deaths += 1
        record.alive = max(0, record.alive - 1)
        record.last_seen_tick = tick
        if record.alive == 0 and lineage_id not in self._extinct_lineages:
            self.extinction_events += 1
            self._extinct_lineages.add(lineage_id)

    def reconcile_alive(self, counts: dict[int, int], tick: int) -> None:
        for lineage_id, record in self.records.items():
            was_alive = record.alive > 0
            record.alive = counts.get(lineage_id, 0)
            if record.alive:
                record.last_seen_tick = tick
                self._extinct_lineages.discard(lineage_id)
            elif was_alive and lineage_id not in self._extinct_lineages:
                self.extinction_events += 1
                self._extinct_lineages.add(lineage_id)

    def alive_counts(self) -> dict[int, int]:
        return {
            lineage_id: record.alive
            for lineage_id, record in self.records.items()
            if record.alive > 0
        }

    def alive_lineage_count(self) -> int:
        return len(self.alive_counts())
