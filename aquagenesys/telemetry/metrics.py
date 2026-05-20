from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from statistics import mean

from aquagenesys.gene_drive.interpreter import dominant_gene_counts
from aquagenesys.organism.life import Organism


@dataclass
class Telemetry:
    births: int = 0
    births_reproduction: int = 0
    births_dormant_revival: int = 0
    births_reseed_debug: int = 0
    deaths_by_cause: Counter[str] = field(default_factory=Counter)
    extinction_events: int = 0
    debug_reseeds: int = 0
    recovery_events: int = 0
    last_recovery_kind: str = "none"
    collapse_cause_guess: str = "none"
    lineage_births: Counter[int] = field(default_factory=Counter)
    lineage_deaths: Counter[int] = field(default_factory=Counter)
    recent_events: list[dict[str, object]] = field(default_factory=list)

    def record_birth(self, lineage_id: int, count: int = 1, *, kind: str = "reproduction") -> None:
        self.births += count
        if kind == "dormant_revival":
            self.births_dormant_revival += count
            self.last_recovery_kind = kind
        elif kind == "debug_reseed":
            self.births_reseed_debug += count
            self.last_recovery_kind = kind
        else:
            self.births_reproduction += count
            self.lineage_births[lineage_id] += count

    def record_death(self, lineage_id: int, cause: str) -> None:
        self.deaths_by_cause[cause] += 1
        self.lineage_deaths[lineage_id] += 1

    def event(self, tick: int, kind: str, **payload: object) -> None:
        self.recent_events.append({"tick": tick, "kind": kind, **payload})
        if len(self.recent_events) > 16:
            del self.recent_events[: len(self.recent_events) - 16]

    def snapshot(
        self,
        tick: int,
        organisms: list[Organism],
        *,
        environmental_viability_score: float = 0.0,
        viable_cells_count: int = 0,
        dead_puddle: bool = False,
    ) -> dict[str, object]:
        population = len(organisms)
        lineages = Counter(org.lineage_id for org in organisms)
        modes = Counter(org.phenotype.metabolism_mode for org in organisms)
        traits = Counter()
        for org in organisms:
            phenotype = org.phenotype
            if phenotype.appendages >= 4:
                traits["many appendages"] += 1
            if phenotype.tail >= 0.58:
                traits["tail-like swimmers"] += 1
            if phenotype.nubbins >= 2:
                traits["nubby drag"] += 1
            if phenotype.toughness >= 0.82:
                traits["armored lumps"] += 1
            if phenotype.photosynthesis >= 0.62:
                traits["surface autotrophy"] += 1
            if phenotype.chemosynthesis >= 0.62:
                traits["vent chemistry"] += 1
            if phenotype.predation >= 0.58:
                traits["biters"] += 1
        species = self._clusters(organisms)
        return {
            "tick": tick,
            "population": population,
            "births": self.births,
            "births_reproduction": self.births_reproduction,
            "births_dormant_revival": self.births_dormant_revival,
            "births_reseed_debug": self.births_reseed_debug,
            "deaths_by_cause": dict(self.deaths_by_cause),
            "extinction_events": self.extinction_events,
            "dead_puddle": dead_puddle,
            "recovery_events": self.recovery_events,
            "last_recovery_kind": self.last_recovery_kind,
            "environmental_viability_score": round(environmental_viability_score, 4),
            "viable_cells_count": viable_cells_count,
            "collapse_cause_guess": self.collapse_cause_guess,
            "average_mutation_load": round(mean([org.phenotype.mutation_load for org in organisms]) if organisms else 0.0, 4),
            "average_energy": round(mean([org.energy for org in organisms]) if organisms else 0.0, 4),
            "dominant_metabolism": modes.most_common(1)[0][0] if modes else "none",
            "dominant_metabolism_label_source": "population_mode",
            "metabolism_counts": dict(modes),
            "dominant_traits": [
                {"trait": trait, "count": count, "share": round(count / max(1, population), 3)}
                for trait, count in traits.most_common(8)
            ],
            "dominant_genes": dominant_gene_counts([org.genome for org in organisms]),
            "lineages": [
                {
                    "lineage": lineage,
                    "population": count,
                    "births": self.lineage_births[lineage],
                    "deaths": self.lineage_deaths[lineage],
                }
                for lineage, count in lineages.most_common(8)
            ],
            "species_clusters": species,
            "reseeds": self.debug_reseeds,
            "recent_events": list(self.recent_events),
        }

    def _clusters(self, organisms: list[Organism]) -> list[dict[str, object]]:
        clusters: dict[tuple[int, ...], list[Organism]] = defaultdict(list)
        for org in organisms:
            key = tuple(int(value * 4.0) for value in org.phenotype.vector())
            clusters[key].append(org)
        ranked = sorted(clusters.items(), key=lambda item: len(item[1]), reverse=True)[:8]
        result: list[dict[str, object]] = []
        for index, (key, members) in enumerate(ranked, start=1):
            result.append(
                {
                    "label": f"S{index}",
                    "size": len(members),
                    "lineages": sorted({member.lineage_id for member in members})[:5],
                    "signature": key,
                    "mode": Counter(member.phenotype.metabolism_mode for member in members).most_common(1)[0][0],
                }
            )
        return result
