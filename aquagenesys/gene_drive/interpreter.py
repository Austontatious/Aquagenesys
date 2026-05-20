from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass

from aquagenesys.gene_drive.expression import Expression, clamp, copy_count_expression
from aquagenesys.gene_drive.genome import Genome
from aquagenesys.gene_drive.primitives import ESSENTIAL_GENES, GENE_NAMES, PRIMITIVES


@dataclass(frozen=True)
class Phenotype:
    size: float
    symmetry: float
    segmentation: float
    toughness: float
    appendage_bias: float
    irregularity: float
    appendages: int
    nubbins: int
    tail: float
    cilia: float
    contractility: float
    burst: float
    turning: float
    speed: float
    drag: float
    sense_light: float
    sense_heat: float
    sense_chem: float
    sense_touch: float
    sense_kin: float
    sense_threat: float
    photosynthesis: float
    chemosynthesis: float
    grazing: float
    predation: float
    scavenging: float
    low_o2: float
    storage: float
    basal_burn: float
    repair: float
    movement_efficiency: float
    growth_cost: float
    reproduction_mode: str
    reproduction_threshold: float
    fecundity: int
    gestation_delay: int
    sexual: float
    hgt: float
    mobile_packets: float
    parasitic_insertion: float
    drive_bias: float
    behavior: dict[str, float]
    tolerances: dict[str, float]
    metabolism_mode: str
    mutation_load: float
    malformation_risk: float
    infertility: float
    color: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def vector(self) -> tuple[float, ...]:
        return (
            self.size / 12.0,
            self.symmetry,
            self.appendage_bias,
            self.tail,
            self.cilia,
            self.photosynthesis,
            self.chemosynthesis,
            self.grazing,
            self.predation,
            self.low_o2,
            self.tolerances["heat"],
            self.tolerances["radiation"],
            self.sexual,
        )


def _expressions(counts: Counter[str]) -> dict[str, Expression]:
    return {
        name: copy_count_expression(
            counts[name],
            optimum=primitive.optimum,
            high=primitive.high,
            extreme=primitive.extreme,
            base_cost=primitive.base_cost,
            essential=name in ESSENTIAL_GENES,
        )
        for name, primitive in PRIMITIVES.items()
    }


def _dominance_adjusted(name: str, expressions: dict[str, Expression], dominance: float, suppression: float) -> float:
    primitive = PRIMITIVES[name]
    expression = expressions[name]
    value = expression.value
    if primitive.dominance >= 0.6:
        value *= 1.0 + dominance * 0.12
    elif primitive.dominance <= 0.4 and expression.value < 0.74:
        value *= 0.58 + dominance * 0.24
    value *= 1.0 - suppression * expression.excess * 0.22
    return clamp(value, 0.0, 1.55)


def _dominant_metabolism(scores: dict[str, float]) -> str:
    best = max(scores, key=scores.get)
    if scores[best] < 0.18:
        return "hungry"
    return best


def _metabolism_color(mode: str, mutation_load: float, lineage_hint: int) -> str:
    base = {
        "photosynthesis": (68, 205, 106),
        "chemosynthesis": (235, 118, 54),
        "grazing": (95, 192, 216),
        "predation": (222, 74, 94),
        "scavenging": (174, 146, 92),
        "hungry": (168, 172, 184),
    }[mode]
    shift = (lineage_hint * 37) % 42
    washed = min(70, int(mutation_load * 80))
    return f"rgb({clamp(base[0] + shift - washed, 40, 255):.0f}, {clamp(base[1] - washed, 35, 255):.0f}, {clamp(base[2] + shift // 2, 45, 255):.0f})"


def assemble_phenotype(genome: Genome, *, lineage_hint: int = 0) -> Phenotype:
    counts = genome.counts
    expressions = _expressions(counts)
    dominance = clamp(expressions["dominance"].value)
    suppression = clamp(expressions["suppression"].value)

    def e(name: str) -> float:
        return _dominance_adjusted(name, expressions, dominance, suppression)

    mutation_tolerance = e("mutation_tolerance")
    repair_accuracy = e("repair_accuracy")
    raw_load = sum(expression.load for expression in expressions.values()) / 3.5
    genome_length_load = max(0.0, (len(genome.tokens) - 95) / 120.0) + max(0.0, (16 - len(genome.tokens)) / 35.0)

    irregularity = clamp(e("irregularity") * 0.78 + expressions["irregularity"].excess * 0.25)
    symmetry = clamp(e("symmetry") - irregularity * 0.38 + e("segmentation") * 0.07)
    appendage_bias = clamp(e("appendage") * (0.55 + symmetry * 0.62), 0.0, 1.35)
    appendage_excess = max(0.0, e("appendage") - 1.0)
    nubbins = int(round((appendage_excess * (1.25 - symmetry) + irregularity * 0.45) * 7.0))
    appendages = int(round(clamp(appendage_bias * 5.5 + e("segmentation") * 2.4 - nubbins * 0.35, 0.0, 12.0)))
    toughness = clamp(e("membrane") + e("defend") * 0.25 + repair_accuracy * 0.12, 0.0, 1.45)
    size = clamp(2.2 + e("size") * 5.4 + e("storage") * 2.3 + toughness * 0.7 - irregularity * 0.8, 1.5, 13.0)

    contractility = e("contractility")
    cilia = e("cilia")
    tail = clamp((e("tail_leverage") + contractility + appendage_bias + symmetry + e("movement_efficiency")) / 5.0)
    burst = clamp(e("burst") * (0.62 + e("storage") * 0.30))
    drag = clamp(irregularity * 0.55 + appendage_excess * (1.0 - symmetry) * 0.70 + toughness * 0.10 + nubbins * 0.045)
    movement_efficiency = clamp(e("movement_efficiency") + repair_accuracy * 0.06, 0.05, 1.35)
    speed = clamp(
        (0.10 + contractility * 0.72 + cilia * 0.42 + tail * 0.94 + burst * 0.34)
        * movement_efficiency
        / (1.0 + size * 0.055 + drag * 0.9),
        0.03,
        2.2,
    )
    turning = clamp(e("turning") * (0.45 + symmetry * 0.8) + cilia * 0.18 - drag * 0.25, 0.05, 1.4)

    light_tolerance = e("light_tolerance")
    heat_tolerance = e("heat_tolerance")
    toxin_tolerance = e("toxin_tolerance")
    oxygen_tolerance = e("oxygen_tolerance")
    radiation_tolerance = e("radiation_tolerance")
    low_o2 = clamp(e("low_o2") + oxygen_tolerance * 0.25)

    photosynthesis = clamp(e("photosynthesis") * (0.50 + light_tolerance * 0.55))
    chemosynthesis = clamp(e("chemosynthesis") * (0.45 + heat_tolerance * 0.45 + low_o2 * 0.15))
    grazing = clamp(e("grazing") * (0.65 + e("graze_behavior") * 0.25))
    predation = clamp(e("predation") * (0.55 + e("bite") * 0.35 + speed * 0.12) - movement_efficiency * 0.08)
    scavenging = clamp(e("scavenging") * (0.65 + e("sense_chem") * 0.18))
    metabolism_scores = {
        "photosynthesis": photosynthesis,
        "chemosynthesis": chemosynthesis,
        "grazing": grazing,
        "predation": predation,
        "scavenging": scavenging,
    }
    metabolism_mode = _dominant_metabolism(metabolism_scores)

    reproduction_values = {
        "budding": e("budding"),
        "spores": e("spores"),
        "sexual": e("sexual"),
    }
    reproduction_mode = max(reproduction_values, key=reproduction_values.get)
    storage = clamp(e("storage"), 0.05, 1.45)
    basal_burn = clamp(0.055 + expressions["basal_burn"].deficit * 0.05 + e("basal_burn") * 0.09 + size * 0.012)
    growth_cost = clamp(e("growth_cost") + size * 0.025)
    fecundity = max(1, min(5, int(round(1 + e("fecundity") * 3.2 + e("spores") * 1.4 - size * 0.08))))
    gestation_delay = max(3, int(round(18 + e("gestation") * 18 - e("fecundity") * 4 + size * 1.5)))
    reproduction_threshold = 18.0 + size * 3.5 + growth_cost * 12.0 + gestation_delay * 0.30 - e("fecundity") * 4.0
    sexual = clamp(reproduction_values["sexual"] * (0.55 + e("mating_window") * 0.35 + e("mate_seek") * 0.18))

    behavior = {
        "approach": clamp(e("approach") + e("sense_chem") * 0.16),
        "avoid": clamp(e("avoid") + e("sense_threat") * 0.20),
        "graze": clamp(e("graze_behavior") + grazing * 0.25),
        "flee": clamp(e("flee") + speed * 0.18),
        "bite": clamp(e("bite") + predation * 0.34),
        "attach": clamp(e("attach") + appendage_bias * 0.16),
        "school": clamp(e("school") + e("sense_kin") * 0.24),
        "hide": clamp(e("hide") + irregularity * 0.12),
        "defend": clamp(e("defend") + toughness * 0.22),
        "mate_seek": clamp(e("mate_seek") + sexual * 0.24),
    }
    tolerances = {
        "toxin": toxin_tolerance,
        "oxygen": oxygen_tolerance,
        "heat": heat_tolerance,
        "light": light_tolerance,
        "radiation": radiation_tolerance,
        "low_o2": low_o2,
    }

    expression_cost = sum(expression.cost for expression in expressions.values()) / 4.0
    malformation = clamp(
        raw_load * (1.0 - mutation_tolerance * 0.28 - repair_accuracy * 0.25)
        + genome_length_load
        + nubbins * 0.018
        + max(0.0, appendage_bias - 1.0) * (1.0 - symmetry) * 0.22
        + irregularity * max(0.0, 0.5 - symmetry) * 0.20,
        0.0,
        1.0,
    )
    mutation_load = clamp(
        expression_cost
        + malformation
        - mutation_tolerance * 0.10
        - repair_accuracy * 0.09
        + expressions["parasitic_insert"].excess * 0.12,
        0.0,
        1.35,
    )
    infertility = clamp(
        expressions["fecundity"].excess * 0.18
        + expressions["gestation"].excess * 0.14
        + malformation * 0.48
        - e("repair") * 0.10
        - e("developmental_phase") * 0.08
    )

    return Phenotype(
        size=size,
        symmetry=symmetry,
        segmentation=e("segmentation"),
        toughness=toughness,
        appendage_bias=appendage_bias,
        irregularity=irregularity,
        appendages=appendages,
        nubbins=nubbins,
        tail=tail,
        cilia=cilia,
        contractility=contractility,
        burst=burst,
        turning=turning,
        speed=speed,
        drag=drag,
        sense_light=e("sense_light"),
        sense_heat=e("sense_heat"),
        sense_chem=e("sense_chem"),
        sense_touch=e("sense_touch"),
        sense_kin=e("sense_kin"),
        sense_threat=e("sense_threat"),
        photosynthesis=photosynthesis,
        chemosynthesis=chemosynthesis,
        grazing=grazing,
        predation=predation,
        scavenging=scavenging,
        low_o2=low_o2,
        storage=storage,
        basal_burn=basal_burn,
        repair=clamp(e("repair") + repair_accuracy * 0.20),
        movement_efficiency=movement_efficiency,
        growth_cost=growth_cost,
        reproduction_mode=reproduction_mode,
        reproduction_threshold=max(14.0, reproduction_threshold),
        fecundity=fecundity,
        gestation_delay=gestation_delay,
        sexual=sexual,
        hgt=clamp(e("hgt") + e("immune_resistance") * 0.05),
        mobile_packets=clamp(e("mobile_packet")),
        parasitic_insertion=clamp(e("parasitic_insert")),
        drive_bias=clamp(e("drive_bias") + dominance * 0.18),
        behavior=behavior,
        tolerances=tolerances,
        metabolism_mode=metabolism_mode,
        mutation_load=mutation_load,
        malformation_risk=malformation,
        infertility=infertility,
        color=_metabolism_color(metabolism_mode, mutation_load, lineage_hint),
    )


def dominant_gene_counts(genomes: list[Genome], limit: int = 8) -> list[dict[str, object]]:
    counter: Counter[str] = Counter()
    for genome in genomes:
        counter.update(genome.tokens)
    total = sum(counter.values()) or 1
    return [
        {
            "gene": gene,
            "family": PRIMITIVES[gene].family.value,
            "copies": count,
            "share": count / total,
        }
        for gene, count in counter.most_common(limit)
        if gene in GENE_NAMES
    ]
