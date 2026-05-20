from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from random import Random
from typing import Iterable

from aquagenesys.gene_drive.primitives import FOUNDER_ARCHETYPES, GENE_NAMES, PRIMITIVES


@dataclass(frozen=True)
class Genome:
    tokens: tuple[str, ...]

    def __post_init__(self) -> None:
        unknown = [token for token in self.tokens if token not in PRIMITIVES]
        if unknown:
            raise ValueError(f"unknown gene tokens: {unknown[:5]}")

    @classmethod
    def from_counts(cls, counts: dict[str, int]) -> "Genome":
        tokens: list[str] = []
        for name, count in counts.items():
            if name not in PRIMITIVES:
                raise ValueError(f"unknown gene token: {name}")
            tokens.extend([name] * max(0, int(count)))
        return cls(tuple(sorted(tokens)))

    @classmethod
    def random_founder(cls, rng: Random, archetype: str | None = None) -> "Genome":
        if archetype is None:
            archetype = rng.choice(tuple(FOUNDER_ARCHETYPES))
        tokens = list(FOUNDER_ARCHETYPES[archetype])
        for token in list(tokens):
            if rng.random() < 0.72:
                tokens.append(token)
            if rng.random() < 0.18:
                tokens.append(token)
        for _ in range(rng.randint(8, 18)):
            tokens.append(rng.choice(GENE_NAMES))
        rng.shuffle(tokens)
        return cls(tuple(tokens))

    @property
    def counts(self) -> Counter[str]:
        return Counter(self.tokens)

    def distance(self, other: "Genome") -> float:
        keys = set(self.counts) | set(other.counts)
        if not keys:
            return 0.0
        total = sum(max(self.counts[key], other.counts[key]) for key in keys)
        diff = sum(abs(self.counts[key] - other.counts[key]) for key in keys)
        return diff / max(1, total)

    def mutated(
        self,
        rng: Random,
        *,
        mutation_rate: float,
        mutation_load: float = 0.0,
        repair: float = 0.0,
    ) -> "Genome":
        effective_rate = max(0.0, mutation_rate * (1.0 + mutation_load * 0.45) * (1.0 - repair * 0.45))
        tokens: list[str] = []
        for token in self.tokens:
            if rng.random() < effective_rate * 0.30:
                continue
            if rng.random() < effective_rate * 0.25:
                tokens.append(rng.choice(GENE_NAMES))
            else:
                tokens.append(token)
            if rng.random() < effective_rate * 0.32:
                tokens.append(token)
        insertion_rolls = 1 + int(rng.random() < effective_rate * 12.0)
        for _ in range(insertion_rolls):
            if rng.random() < effective_rate * 1.8:
                tokens.append(rng.choice(GENE_NAMES))
        if not tokens:
            tokens.append(rng.choice(GENE_NAMES))
        rng.shuffle(tokens)
        return Genome(tuple(tokens[:180]))

    def with_insertions(self, inserts: Iterable[str]) -> "Genome":
        tokens = list(self.tokens)
        for token in inserts:
            if token in PRIMITIVES:
                tokens.append(token)
        return Genome(tuple(tokens[:180]))


def recombine_genomes(
    rng: Random,
    parent_a: Genome,
    parent_b: Genome,
    *,
    mutation_rate: float,
    drive_bias: float,
    mutation_load: float,
    repair: float,
) -> Genome:
    counts_a = parent_a.counts
    counts_b = parent_b.counts
    child: list[str] = []
    for gene in sorted(set(counts_a) | set(counts_b)):
        copies = max(counts_a[gene], counts_b[gene])
        primitive = PRIMITIVES[gene]
        bias = drive_bias * primitive.dominance
        for _ in range(copies):
            inherited = 0
            if rng.random() < 0.50 + 0.20 * bias and counts_a[gene] > 0:
                inherited += 1
            if rng.random() < 0.50 + 0.20 * bias and counts_b[gene] > 0:
                inherited += 1
            if inherited == 0 and rng.random() < 0.08 + 0.08 * bias:
                inherited = 1
            child.extend([gene] * min(inherited, 2))
    if not child:
        child.extend(parent_a.tokens[: max(1, len(parent_a.tokens) // 2)])
    rng.shuffle(child)
    return Genome(tuple(child[:180])).mutated(
        rng,
        mutation_rate=mutation_rate,
        mutation_load=mutation_load,
        repair=repair,
    )
