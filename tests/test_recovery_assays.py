from __future__ import annotations

from evals.recovery_assays import run_recovery_assays


def test_recovery_assays_are_programmatic_and_explain_recovery() -> None:
    results = run_recovery_assays(seeds=[711, 712], ticks=90)
    assert results["schema"] == "aquagenesys.recovery_assays.v1"
    assays = results["assays"]
    assert assays["bottleneck_recovery"]["recovery_rate"] > 0
    assert assays["bottleneck_recovery"]["no_god_mode_reseed"] is True
    assert assays["egg_bank_resilience"]["dormant_state_rate"] > 0
    assert assays["egg_bank_resilience"]["dormant_to_hatched_rate"] > 0
    assert assays["egg_bank_resilience"]["no_instant_adult_rescue"] is True
    assert assays["reproduction_gates"]["low_global_population_not_overcrowded"] is True
    assert assays["density_crowding"]["local_clusters_can_still_crowd"] is True
    assert assays["resource_rebound"]["resource_opportunity"] is True
    assert assays["resource_rebound"]["fish_created_directly"] is False
    assert assays["behavior_payoff"]["actions_differ"] is True
    assert assays["behavior_payoff"]["biology_not_overridden"] is True
    assert assays["ai_deliberation"]["live_model_required"] is False
    assert results["conclusion"]["mechanics_tuning_recommended"] is False
