from __future__ import annotations

from dataclasses import replace
from random import Random

from aquagenesys.agents import FishGenome, derive_life_history
from aquagenesys.simulation import AquagenesysSimulation, SimulationConfig
from aquagenesys.storage import segment_jsonl_runs


class LowRandom(Random):
    def random(self) -> float:
        return 0.0


class HighRandom(Random):
    def random(self) -> float:
        return 1.0


def mature_for_reproduction(sim: AquagenesysSimulation, *, allele_count: int = 0, singleton: bool = False):
    parent = sim.fish[0]
    parent.genome = replace(
        parent.genome,
        parthenogenesis_alleles=allele_count,
        parthenogenesis_bias=0.26 if allele_count else 0.0,
        dormancy_bias=0.86,
        reproduction_rate=0.92,
        mutation_load=0.04,
    )
    life = parent.life_history
    parent.age = life.senescence_start_ticks if allele_count else life.maturity_age_ticks + 4
    parent.energy = 94.0
    parent.health = 0.96
    parent.stress = 0.02
    parent.reproductive_drive = 0.98
    parent.reproduction_cooldown = 0
    parent.x = sim.config.width / 2.0
    parent.y = sim.config.height / 2.0
    if singleton:
        sim.fish = [parent]
    else:
        mate = sim.fish[1]
        mate.genome = replace(mate.genome, metabolism=parent.genome.metabolism)
        mate.x = parent.x + 1.0
        mate.y = parent.y + 1.0
    return parent


def good_perception(sim: AquagenesysSimulation, parent):
    perception = sim._sense(parent)
    perception.reproduction_score = 0.92
    perception.resource_score = 0.88
    perception.crowding = 0.0
    return perception


def test_life_history_derivation_is_deterministic_and_strategy_varies() -> None:
    rng_a = Random(2)
    rng_b = Random(2)
    grazer = FishGenome.founder(rng_a, lineage_id=1, archetype="silt_grazer")
    predator = FishGenome.founder(rng_b, lineage_id=2, archetype="mud_stalker")
    grazer_life = derive_life_history(grazer)
    predator_life = derive_life_history(predator)
    assert derive_life_history(grazer).payload() == grazer_life.payload()
    assert grazer_life.maturity_age_ticks < predator_life.maturity_age_ticks
    assert grazer_life.expected_lifespan_ticks < predator_life.expected_lifespan_ticks
    assert grazer_life.base_clutch_size > predator_life.base_clutch_size
    assert 0.0 <= grazer_life.dormancy_bias <= 1.0
    assert grazer_life.payload()["brood_strategy"]


def test_brood_reproduction_lays_energy_costed_egg_clutch() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=101, width=34, height=22, initial_population=2, max_population=30, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.rng = LowRandom(5)
    parent = mature_for_reproduction(sim)
    before = parent.energy
    result = sim._maybe_reproduce(parent, good_perception(sim, parent))
    assert result.eggs
    assert len(result.eggs) > 1
    assert parent.energy < before
    assert parent.energy > 20.0
    assert parent.reproduction_cooldown > 0
    assert result.eggs[0].parent_ids == (parent.fish_id,)
    sim.close()


def test_bad_environment_blocks_reproduction_with_gate_reason() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=102, width=30, height=20, initial_population=2, deliberation_enabled=False, archive_every_ticks=0)
    )
    parent = mature_for_reproduction(sim)
    perception = good_perception(sim, parent)
    perception.reproduction_score = 0.05
    result = sim._maybe_reproduce(parent, perception)
    assert not result.eggs
    assert parent.last_reproduction_gate == "bad_environment"
    assert sim.reproduction_gate_reasons["bad_environment"] == 1
    sim.close()


def test_eggs_persist_after_parent_death_and_hatch_under_good_conditions() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=103, width=34, height=22, initial_population=2, max_population=30, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.rng = LowRandom(7)
    parent = mature_for_reproduction(sim)
    result = sim._maybe_reproduce(parent, good_perception(sim, parent))
    egg = result.eggs[0]
    sim.eggs = [egg]
    sim.fish = []
    sim.step()
    assert sim.eggs
    assert sim.state()["telemetry"]["biosphere_state"] == "dormant"
    assert sim.state()["telemetry"]["dead_puddle"] is False
    egg.age_ticks = egg.gestation_ticks
    egg.viability = 0.98
    egg.dormant = False
    egg.state = "gestating"
    sim.step()
    assert sim.fish
    assert sim.fish[0].lineage_id == egg.lineage_id
    assert sim.fish[0].generation == egg.generation
    assert sim.state()["telemetry"]["biosphere_state"] == "active"
    sim.close()


def test_dormant_egg_decay_is_slower_than_active_decay() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=104, width=34, height=22, initial_population=2, deliberation_enabled=False, archive_every_ticks=0)
    )
    parent = mature_for_reproduction(sim)
    perception = good_perception(sim, parent)
    instruction_genome, taught_skills, patch_decision, skill_inheritance = sim._offspring_instruction_seed(
        parent,
        child_generation=parent.generation + 1,
        parthenogenetic=False,
    )
    egg = sim._create_egg(
        parent,
        parent.genome,
        instruction_genome,
        taught_skills,
        perception,
        9.0,
        parthenogenetic=False,
        patch_decision=patch_decision,
        skill_inheritance=skill_inheritance,
    )
    active = replace(egg, egg_id=500, dormant=False, state="gestating", viability=0.8)
    dormant = replace(egg, egg_id=501, dormant=True, state="dormant", viability=0.8)
    sim.rng = HighRandom(1)
    sim.eggs = [active, dormant]
    sim.fish = []
    sim.step()
    assert sim.eggs[1].viability > sim.eggs[0].viability
    sim.close()


def test_final_singleton_requires_parthenogenesis_trait() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=105, width=30, height=20, initial_population=1, deliberation_enabled=False, archive_every_ticks=0)
    )
    parent = mature_for_reproduction(sim, allele_count=0, singleton=True)
    result = sim._maybe_reproduce(parent, good_perception(sim, parent))
    assert not result.eggs
    assert result.reason == "parthenogenesis_not_available"
    sim.close()


def test_final_singleton_with_trait_can_deposit_bounded_clonal_eggs() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=106, width=30, height=20, initial_population=1, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.rng = LowRandom(3)
    parent = mature_for_reproduction(sim, allele_count=2, singleton=True)
    before = parent.energy
    result = sim._maybe_reproduce(parent, good_perception(sim, parent))
    assert result.mode == "parthenogenesis"
    assert result.eggs
    assert all(egg.parthenogenetic for egg in result.eggs)
    assert parent.energy < before
    sim.close()


def test_true_extinction_requires_no_adults_and_no_viable_eggs() -> None:
    dormant = AquagenesysSimulation(
        SimulationConfig(seed=107, width=30, height=20, initial_population=1, deliberation_enabled=False, archive_every_ticks=0)
    )
    dormant.rng = LowRandom(4)
    parent = mature_for_reproduction(dormant, allele_count=2, singleton=True)
    egg = dormant._maybe_reproduce(parent, good_perception(dormant, parent)).eggs[0]
    dormant.eggs = [egg]
    dormant.fish = []
    dormant.step()
    assert dormant.state()["telemetry"]["biosphere_state"] == "dormant"
    assert dormant.state()["telemetry"]["dead_puddle"] is False
    dormant.close()

    extinct = AquagenesysSimulation(SimulationConfig(seed=108, width=24, height=18, initial_population=0, deliberation_enabled=False))
    extinct.run(2)
    assert extinct.state()["telemetry"]["biosphere_state"] == "extinct"
    assert extinct.state()["telemetry"]["dead_puddle"] is True
    extinct.close()


def test_detritus_rebound_strengthens_lower_trophic_fields_without_spawning_fish() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=109, width=24, height=18, initial_population=1, deliberation_enabled=False, archive_every_ticks=0)
    )
    fish = sim.fish[0]
    before = sim.environment.sample(fish.x, fish.y)
    sim._recycle_dead(fish, "environment")
    after = sim.environment.sample(fish.x, fish.y)
    assert after.decomposition > before.decomposition
    assert after.nutrients >= before.nutrients
    assert len(sim.fish) == 1
    sim.close()


def test_lifecycle_archive_has_run_id_and_run_segmentation(tmp_path) -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=110, width=28, height=18, initial_population=2, deliberation_enabled=False, archive_dir=str(tmp_path), archive_every_ticks=1)
    )
    sim.step()
    sim.reset()
    sim.step()
    segments = segment_jsonl_runs(tmp_path / "fish_state.jsonl")
    assert len(segments) == 2
    assert all(segment["run_id"] for segment in segments)
    assert (tmp_path / "lifecycle_events.jsonl").exists()
    assert '"run_id"' in (tmp_path / "fish_state.jsonl").read_text(encoding="utf-8")
    sim.close()
