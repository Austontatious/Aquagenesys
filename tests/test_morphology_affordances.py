from __future__ import annotations

from dataclasses import replace
from random import Random

from aquagenesys.agents import FishGenome
from aquagenesys.agents.morphology import (
    AppendageLoci,
    ArmorSkinLoci,
    BodyScaffoldLoci,
    ChemicalLoci,
    DevelopmentLoci,
    HeadMouthLoci,
    MorphologyGenome,
    derive_observational_labels,
    interpret_morphology,
)
from aquagenesys.simulation import AquagenesysSimulation, SimulationConfig


class LowRandom(Random):
    def random(self) -> float:
        return 0.0


def test_morphology_construction_is_bounded_and_hash_stable() -> None:
    rng_a = Random(400)
    rng_b = Random(400)
    genome_a = FishGenome.founder(rng_a, lineage_id=1, archetype="glass_filter")
    genome_b = FishGenome.founder(rng_b, lineage_id=1, archetype="glass_filter")
    assert genome_a.morphology.payload() == genome_b.morphology.payload()
    assert genome_a.morphology_hash == genome_b.morphology_hash
    assert genome_a.morphology_hash.startswith("morph_")
    payload = genome_a.morphology.payload()
    for module in ("body", "head_mouth", "appendage", "armor_skin", "chemical", "sensory", "development"):
        assert module in payload
    assert 0 <= payload["appendage"]["appendage_count"] <= 14
    assert 0.0 <= genome_a.morphology_affordances().viability_index <= 1.0


def test_affordance_interpreter_tracks_expected_directions() -> None:
    base = MorphologyGenome.balanced()
    base_aff = interpret_morphology(base)

    bite = replace(base, head_mouth=replace(base.head_mouth, head_mass_ratio=0.94, mouth_force=1.0, mouth_aperture=0.92))
    bite_aff = interpret_morphology(bite)
    assert bite_aff.bite_force > base_aff.bite_force
    assert bite_aff.oxygen_cost > base_aff.oxygen_cost

    appendage = replace(base, appendage=AppendageLoci(appendage_count=10, appendage_length=1.0, appendage_flexibility=0.92, appendage_strength=0.82, propulsion_surface=0.40))
    appendage_aff = interpret_morphology(appendage)
    assert appendage_aff.reach > base_aff.reach
    assert appendage_aff.grip > base_aff.grip
    assert appendage_aff.drag > base_aff.drag

    armored = replace(base, armor_skin=ArmorSkinLoci(armor_density=0.95, spine_density=0.72, tissue_vulnerability=0.18, mucous_barrier=0.45))
    armored_aff = interpret_morphology(armored)
    assert armored_aff.armor_protection > base_aff.armor_protection
    assert armored_aff.drag > base_aff.drag

    chemical = replace(base, chemical=ChemicalLoci(chemical_gland_capacity=0.90, chemical_delivery_efficiency=0.82, toxin_resistance=0.44, self_toxicity=0.52))
    chemical_aff = interpret_morphology(chemical)
    assert chemical_aff.toxin_payload > base_aff.toxin_payload
    assert chemical_aff.toxin_self_cost > base_aff.toxin_self_cost

    filterer = replace(base, head_mouth=replace(base.head_mouth, mouth_suction=0.92, filter_surface_area=1.0, gut_capacity=0.88))
    filter_aff = interpret_morphology(filterer)
    assert filter_aff.filter_rate > base_aff.filter_rate
    assert filter_aff.feeding_throughput > base_aff.feeding_throughput


def test_extreme_morphology_has_costs_without_hard_banning_all_weirdness() -> None:
    base = MorphologyGenome.balanced()
    base_aff = interpret_morphology(base)
    malformed = MorphologyGenome(
        body=BodyScaffoldLoci(body_mass=1.16, body_length=0.42, body_depth=1.08, body_axis_length=0.42, body_axis_depth=1.08, surface_area=0.72, soft_tissue_ratio=0.88, reserve_capacity=0.44),
        head_mouth=HeadMouthLoci(head_mass_ratio=1.12, mouth_position="terminal", mouth_aperture=0.28, mouth_force=0.22, mouth_suction=0.18, gut_capacity=0.24, filter_surface_area=0.12),
        appendage=AppendageLoci(appendage_count=14, appendage_length=1.25, appendage_flexibility=0.22, appendage_strength=0.20, propulsion_surface=0.12),
        armor_skin=ArmorSkinLoci(armor_density=0.06, spine_density=0.02, tissue_vulnerability=1.0, mucous_barrier=0.12),
        chemical=ChemicalLoci(chemical_gland_capacity=0.82, chemical_delivery_efficiency=0.10, toxin_resistance=0.12, self_toxicity=0.92),
        development=DevelopmentLoci(developmental_stability=0.18, mutation_volatility=0.82, growth_cost=0.95, juvenile_fragility=0.98, reproduction_cost=0.90, oxygen_demand=1.0),
    )
    malformed_aff = interpret_morphology(malformed)
    assert malformed_aff.drag > base_aff.drag
    assert malformed_aff.metabolic_burden > base_aff.metabolic_burden
    assert malformed_aff.viability_index < base_aff.viability_index

    supported_filter_weird = replace(
        base,
        body=replace(base.body, body_mass=0.92, reserve_capacity=0.88),
        head_mouth=replace(base.head_mouth, mouth_position="filter_slot", mouth_suction=0.95, filter_surface_area=1.0, gut_capacity=0.94),
        development=replace(base.development, developmental_stability=0.78, oxygen_demand=0.58),
    )
    supported_aff = interpret_morphology(supported_filter_weird)
    assert supported_aff.filter_rate > 0.65
    assert supported_aff.feeding_throughput > malformed_aff.feeding_throughput
    assert supported_aff.viability_index > malformed_aff.viability_index


def test_morphology_mutates_and_is_inherited_through_reproduction() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=410, width=34, height=22, initial_population=2, max_population=30, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.rng = LowRandom(410)
    parent = sim.fish[0]
    mate = sim.fish[1]
    parent.genome = replace(parent.genome, reproduction_rate=0.97, dormancy_bias=0.88, mutation_load=0.03)
    mate.genome = replace(mate.genome, metabolism=parent.genome.metabolism)
    mate.x = parent.x + 1.0
    mate.y = parent.y + 1.0
    parent.age = parent.life_history.maturity_age_ticks + 10
    parent.energy = 96.0
    parent.health = 0.97
    parent.stress = 0.02
    parent.reproductive_drive = 0.99
    parent.reproduction_cooldown = 0
    perception = sim._sense(parent)
    perception.reproduction_score = 0.95
    perception.resource_score = 0.92
    perception.crowding = 0.0
    result = sim._maybe_reproduce(parent, perception)
    offspring_genomes = [child.genome for child in result.newborns] + [egg.genome for egg in result.eggs]
    assert offspring_genomes
    assert all(genome.morphology_hash.startswith("morph_") for genome in offspring_genomes)
    assert all(genome.morphology.payload()["schema"] == "aquagenesys.morphology.v1" for genome in offspring_genomes)
    assert any(genome.morphology_hash != parent.genome.morphology_hash for genome in offspring_genomes)
    sim.close()


def test_rendering_data_reflects_morphology_loci() -> None:
    base = MorphologyGenome.balanced()
    weird = replace(
        base,
        head_mouth=replace(base.head_mouth, head_mass_ratio=0.98, mouth_force=0.92),
        appendage=AppendageLoci(appendage_count=9, appendage_length=0.94, appendage_flexibility=0.86, appendage_strength=0.78, propulsion_surface=0.34),
        armor_skin=replace(base.armor_skin, armor_density=0.86, spine_density=0.72),
        chemical=replace(base.chemical, chemical_gland_capacity=0.72, chemical_delivery_efficiency=0.62),
    )
    genome = replace(FishGenome.founder(Random(420), lineage_id=1, archetype="mud_stalker"), morphology=weird)
    phenotype = genome.phenotype_payload(compact=True)
    render = phenotype["morphology"]
    assert render["appendage_count"] == 9
    assert render["head_scale"] > 1.0
    assert render["armor_density"] > 0.8
    assert render["spine_density"] > 0.7
    assert render["chemical_marker"] > 0.5
    assert derive_observational_labels(weird)


def test_state_exposes_morphology_without_frame_bloat() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=430, width=34, height=22, initial_population=8, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.run(4)
    state = sim.state()
    frame = sim.frame_state()
    assert state["schema"] == "aquagenesys.state.v13"
    assert state["morphology"]["schema"] == "aquagenesys.morphology.v1"
    assert state["morphology"]["organisms"]
    first = state["morphology"]["organisms"][0]
    assert first["morphology_hash"].startswith("morph_")
    assert first["affordances"]["viability_index"] > 0.0
    assert "morphology" not in frame
    assert "fields" not in frame["environment"]
    assert frame["fish"][0]["phenotype"]["morphology"]["morphology_hash"].startswith("morph_")
    assert len(str(frame)) < len(str(state)) * 0.55
    sim.close()


def test_morphology_affects_ecological_cost_and_feeding() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=440, width=34, height=22, initial_population=2, max_population=20, deliberation_enabled=False, archive_every_ticks=0)
    )
    low_drag = sim.fish[0]
    high_drag = sim.fish[1]
    high_drag.genome = replace(
        high_drag.genome,
        morphology=replace(
            high_drag.genome.morphology,
            appendage=AppendageLoci(appendage_count=12, appendage_length=1.1, appendage_flexibility=0.72, appendage_strength=0.50, propulsion_surface=0.12),
            armor_skin=replace(high_drag.genome.morphology.armor_skin, armor_density=0.86, spine_density=0.50),
            development=replace(high_drag.genome.morphology.development, oxygen_demand=0.92, growth_cost=0.82),
        ),
    )
    for fish in (low_drag, high_drag):
        fish.x = 17.0
        fish.y = 11.0
        fish.vx = 0.0
        fish.vy = 0.0
        fish.energy = 70.0
        fish.health = 0.92
        fish.hunger = 0.55
        fish.stress = 0.04
    action = low_drag.last_decision.__class__("escape", 1.0, 0.0, 0.9, "habit", "test movement")
    before_low = low_drag.energy
    sim._apply_action(low_drag, action, sim._sense(low_drag), {})
    low_cost = before_low - low_drag.energy
    before_high = high_drag.energy
    sim._apply_action(high_drag, action, sim._sense(high_drag), {})
    high_cost = before_high - high_drag.energy
    assert high_drag.morphology_affordances.drag > low_drag.morphology_affordances.drag
    assert high_cost > low_cost

    filterer = low_drag
    filterer.genome = replace(
        filterer.genome,
        metabolism="filter",
        morphology=replace(
            filterer.genome.morphology,
            head_mouth=replace(filterer.genome.morphology.head_mouth, mouth_position="filter_slot", mouth_suction=0.96, filter_surface_area=1.0, gut_capacity=0.92),
        ),
    )
    ix = int(round(filterer.x))
    iy = int(round(filterer.y))
    sim.environment.fields["plankton"][iy][ix] = 1.0
    filterer.energy = 40.0
    gain = sim._feed_from_environment(filterer)
    assert gain > 0.0
    assert filterer.energy > 40.0
    sim.close()
