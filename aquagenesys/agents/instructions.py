from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from random import Random
from typing import Any


RISK_POSTURES = ("cautious", "balanced", "bold")
FORAGE_STRATEGIES = ("nearest_food", "safe_food", "high_yield_patch", "follow_success_memory", "opportunistic_scavenge")
THREAT_STRATEGIES = ("flee_fast", "hide", "school", "freeze", "distance_then_resume")
SOCIAL_STRATEGIES = ("solitary", "school_near_kin", "school_any", "avoid_crowding", "territorial")
REPRODUCTION_STRATEGIES = ("early_and_often", "energy_reserve_first", "wait_for_good_conditions", "clutch_when_safe", "emergency_last_chance")
EXPLORATION_STRATEGIES = ("local_patch", "edge_probe", "random_walk", "memory_guided", "novelty_seek")
ENERGY_STRATEGIES = ("conserve", "balanced", "burst_then_recover")
TEACHING_STYLES = ("none", "conservative", "opportunistic", "bottleneck", "explorer")
MEMORY_BIASES = ("prefer_recent_success", "prefer_safe_outcomes", "prefer_energy_gain", "prefer_social_success")
SKILL_TYPES = ("forage", "threat", "social", "explore", "reproduce", "energy")
PATCH_TYPES = ("offspring_behavior_prior",)
ACTION_BIASES = {
    "forage": FORAGE_STRATEGIES,
    "threat": THREAT_STRATEGIES,
    "social": SOCIAL_STRATEGIES,
    "explore": EXPLORATION_STRATEGIES,
    "reproduce": REPRODUCTION_STRATEGIES,
    "energy": ENERGY_STRATEGIES,
}
FORBIDDEN_TOKENS = (
    "shell",
    "bash",
    "filesystem",
    "file",
    "network",
    "socket",
    "repo",
    "server",
    "tool",
    "exec",
    "python",
    "teleport",
    "spawn food",
    "disable death",
    "ignore energy",
    "edit code",
    "self modify",
    "self-modify",
)
SCHEMA_VERSION = "aquagenesys.behavior_instruction.v1"


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def stable_hash(payload: dict[str, Any], *, length: int = 16) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()[:length]


def _neighbor_enum(value: str, options: tuple[str, ...], rng: Random) -> str:
    index = options.index(value) if value in options else len(options) // 2
    index = max(0, min(len(options) - 1, index + rng.choice([-1, 1])))
    return options[index]


def _short(text: object, limit: int = 64) -> str:
    cleaned = str(text or "").strip().replace("\n", " ")
    return cleaned[:limit]


@dataclass(frozen=True)
class TaughtSkill:
    skill_id: str
    source_parent_id: int
    source_lineage_id: int
    created_tick: int
    generation_created: int
    skill_type: str
    trigger: str
    action_bias: str
    confidence: float
    energy_cost_bias: float
    risk_bias: float
    memory_bias: str
    ttl_generations: int
    decay: float
    rationale_tag: str = ""
    patch_id: str = ""

    @property
    def skill_hash(self) -> str:
        return stable_hash(self.payload(include_hash=False), length=16)

    def expired_for_generation(self, generation: int) -> bool:
        return generation - self.generation_created >= self.ttl_generations

    def payload(self, *, include_hash: bool = True, compact: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "skill_id": self.skill_id,
            "source_parent_id": self.source_parent_id,
            "source_lineage_id": self.source_lineage_id,
            "created_tick": self.created_tick,
            "generation_created": self.generation_created,
            "skill_type": self.skill_type,
            "trigger": self.trigger,
            "action_bias": self.action_bias,
            "confidence": round(self.confidence, 3),
            "energy_cost_bias": round(self.energy_cost_bias, 3),
            "risk_bias": round(self.risk_bias, 3),
            "memory_bias": self.memory_bias,
            "ttl_generations": self.ttl_generations,
            "decay": round(self.decay, 3),
            "rationale_tag": self.rationale_tag,
            "patch_id": self.patch_id,
        }
        if include_hash:
            payload["skill_hash"] = self.skill_hash
        if compact:
            return {
                "skill_id": self.skill_id,
                "skill_hash": self.skill_hash,
                "skill_type": self.skill_type,
                "trigger": self.trigger,
                "action_bias": self.action_bias,
                "ttl_generations": self.ttl_generations,
            }
        return payload


@dataclass(frozen=True)
class BehaviorInstructionGenome:
    schema_version: str = SCHEMA_VERSION
    policy_id: str = "balanced-generalist"
    risk_posture: str = "balanced"
    forage_strategy: str = "nearest_food"
    threat_strategy: str = "flee_fast"
    social_strategy: str = "school_any"
    reproduction_strategy: str = "wait_for_good_conditions"
    exploration_strategy: str = "random_walk"
    energy_strategy: str = "balanced"
    teaching_style: str = "none"
    memory_bias: str = "prefer_recent_success"
    model_deliberation_bias: float = 0.0
    allowed_skill_slots: int = 2
    mutation_rate: float = 0.08
    risk_bias: float = 0.0
    energy_bias: float = 0.0
    accepted_patch_ids: tuple[str, ...] = field(default_factory=tuple)
    rejected_patch_ids: tuple[str, ...] = field(default_factory=tuple)
    inherited_from_policy_hash: str = ""

    @classmethod
    def founder(cls, rng: Random, *, biological_genome: Any) -> "BehaviorInstructionGenome":
        risk = getattr(biological_genome, "risk_tolerance", 0.5)
        social = getattr(biological_genome, "sociality", 0.5)
        curiosity = getattr(biological_genome, "curiosity", 0.5)
        reproduction = getattr(biological_genome, "reproduction_rate", 0.5)
        metabolism = getattr(biological_genome, "metabolism", "omnivore")
        risk_posture = "cautious" if risk < 0.42 else "bold" if risk > 0.62 else "balanced"
        forage_strategy = {
            "filter": "safe_food",
            "grazer": "nearest_food",
            "scavenger": "opportunistic_scavenge",
            "predator": "high_yield_patch",
        }.get(metabolism, "follow_success_memory" if rng.random() < 0.35 else "nearest_food")
        threat_strategy = "hide" if risk_posture == "cautious" else "distance_then_resume" if risk_posture == "balanced" else "flee_fast"
        social_strategy = "school_near_kin" if social > 0.62 else "solitary" if social < 0.30 else "school_any"
        reproduction_strategy = "early_and_often" if reproduction > 0.58 else "energy_reserve_first" if reproduction < 0.40 else "wait_for_good_conditions"
        exploration_strategy = "novelty_seek" if curiosity > 0.64 else "local_patch" if risk_posture == "cautious" else "random_walk"
        energy_strategy = "conserve" if getattr(biological_genome, "body_size", 0.7) > 0.86 else "burst_then_recover" if risk_posture == "bold" else "balanced"
        teaching_style = "conservative" if risk_posture == "cautious" else "explorer" if exploration_strategy == "novelty_seek" else "opportunistic"
        memory_bias = "prefer_safe_outcomes" if risk_posture == "cautious" else "prefer_energy_gain" if forage_strategy == "high_yield_patch" else "prefer_recent_success"
        policy = cls(
            policy_id=f"{risk_posture}-{forage_strategy}-{energy_strategy}",
            risk_posture=risk_posture,
            forage_strategy=forage_strategy,
            threat_strategy=threat_strategy,
            social_strategy=social_strategy,
            reproduction_strategy=reproduction_strategy,
            exploration_strategy=exploration_strategy,
            energy_strategy=energy_strategy,
            teaching_style=teaching_style,
            memory_bias=memory_bias,
            model_deliberation_bias=round((getattr(biological_genome, "deliberation_chance", 0.10) - 0.12) * 0.45, 4),
            allowed_skill_slots=2 + (1 if getattr(biological_genome, "memory_span", 12) >= 15 else 0),
            mutation_rate=clamp(0.055 + getattr(biological_genome, "mutation_load", 0.06) * 0.45, 0.02, 0.18),
            risk_bias=round((risk - 0.5) * 0.22, 4),
            energy_bias=0.0,
        )
        return policy.normalized()

    @property
    def policy_hash(self) -> str:
        return stable_hash(
            {
                "schema_version": self.schema_version,
                "policy_id": self.policy_id,
                "risk_posture": self.risk_posture,
                "forage_strategy": self.forage_strategy,
                "threat_strategy": self.threat_strategy,
                "social_strategy": self.social_strategy,
                "reproduction_strategy": self.reproduction_strategy,
                "exploration_strategy": self.exploration_strategy,
                "energy_strategy": self.energy_strategy,
                "teaching_style": self.teaching_style,
                "memory_bias": self.memory_bias,
                "model_deliberation_bias": round(self.model_deliberation_bias, 4),
                "allowed_skill_slots": self.allowed_skill_slots,
                "mutation_rate": round(self.mutation_rate, 4),
                "risk_bias": round(self.risk_bias, 4),
                "energy_bias": round(self.energy_bias, 4),
            },
            length=16,
        )

    @property
    def policy_hash_short(self) -> str:
        return self.policy_hash[:8]

    @property
    def policy_label(self) -> str:
        bits = []
        if self.risk_posture != "balanced":
            bits.append(self.risk_posture)
        if self.forage_strategy in {"safe_food", "high_yield_patch", "opportunistic_scavenge"}:
            bits.append(self.forage_strategy.replace("_", "-"))
        if self.social_strategy == "school_near_kin":
            bits.append("kin-schooler")
        if self.energy_strategy == "conserve":
            bits.append("energy-saver")
        if self.exploration_strategy == "novelty_seek":
            bits.append("novelty-seeker")
        return ", ".join(bits[:3]) or "balanced"

    def policy_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "risk_posture": self.risk_posture,
            "forage_strategy": self.forage_strategy,
            "threat_strategy": self.threat_strategy,
            "social_strategy": self.social_strategy,
            "reproduction_strategy": self.reproduction_strategy,
            "exploration_strategy": self.exploration_strategy,
            "energy_strategy": self.energy_strategy,
            "teaching_style": self.teaching_style,
            "memory_bias": self.memory_bias,
            "model_deliberation_bias": round(self.model_deliberation_bias, 4),
            "allowed_skill_slots": self.allowed_skill_slots,
            "mutation_rate": round(self.mutation_rate, 4),
            "risk_bias": round(self.risk_bias, 4),
            "energy_bias": round(self.energy_bias, 4),
            "accepted_patch_ids": list(self.accepted_patch_ids[-8:]),
            "rejected_patch_ids": list(self.rejected_patch_ids[-8:]),
            "inherited_from_policy_hash": self.inherited_from_policy_hash,
        }
        if include_hash:
            payload["policy_hash"] = self.policy_hash
            payload["policy_hash_short"] = self.policy_hash_short
            payload["policy_label"] = self.policy_label
        return payload

    def compact_payload(self) -> dict[str, Any]:
        return {
            "policy_hash_short": self.policy_hash_short,
            "policy_label": self.policy_label,
            "risk_posture": self.risk_posture,
            "forage_strategy": self.forage_strategy,
            "threat_strategy": self.threat_strategy,
            "social_strategy": self.social_strategy,
            "energy_strategy": self.energy_strategy,
            "exploration_strategy": self.exploration_strategy,
            "teaching_style": self.teaching_style,
        }

    def normalized(self) -> "BehaviorInstructionGenome":
        return BehaviorInstructionGenome(
            schema_version=SCHEMA_VERSION,
            policy_id=_short(self.policy_id, 48) or "balanced-generalist",
            risk_posture=self.risk_posture if self.risk_posture in RISK_POSTURES else "balanced",
            forage_strategy=self.forage_strategy if self.forage_strategy in FORAGE_STRATEGIES else "nearest_food",
            threat_strategy=self.threat_strategy if self.threat_strategy in THREAT_STRATEGIES else "flee_fast",
            social_strategy=self.social_strategy if self.social_strategy in SOCIAL_STRATEGIES else "school_any",
            reproduction_strategy=self.reproduction_strategy
            if self.reproduction_strategy in REPRODUCTION_STRATEGIES
            else "wait_for_good_conditions",
            exploration_strategy=self.exploration_strategy if self.exploration_strategy in EXPLORATION_STRATEGIES else "random_walk",
            energy_strategy=self.energy_strategy if self.energy_strategy in ENERGY_STRATEGIES else "balanced",
            teaching_style=self.teaching_style if self.teaching_style in TEACHING_STYLES else "none",
            memory_bias=self.memory_bias if self.memory_bias in MEMORY_BIASES else "prefer_recent_success",
            model_deliberation_bias=clamp(float(self.model_deliberation_bias), -0.22, 0.22),
            allowed_skill_slots=max(0, min(4, int(self.allowed_skill_slots))),
            mutation_rate=clamp(float(self.mutation_rate), 0.01, 0.22),
            risk_bias=clamp(float(self.risk_bias), -0.22, 0.22),
            energy_bias=clamp(float(self.energy_bias), -0.22, 0.22),
            accepted_patch_ids=tuple(_short(item, 32) for item in self.accepted_patch_ids[-8:]),
            rejected_patch_ids=tuple(_short(item, 32) for item in self.rejected_patch_ids[-8:]),
            inherited_from_policy_hash=_short(self.inherited_from_policy_hash, 24),
        )

    def mutated(self, rng: Random, *, parent_hash: str = "") -> "BehaviorInstructionGenome":
        policy = self.normalized()
        values = policy.__dict__.copy()
        rate = policy.mutation_rate
        if rng.random() < rate:
            field_name, options = rng.choice(
                [
                    ("risk_posture", RISK_POSTURES),
                    ("forage_strategy", FORAGE_STRATEGIES),
                    ("threat_strategy", THREAT_STRATEGIES),
                    ("social_strategy", SOCIAL_STRATEGIES),
                    ("reproduction_strategy", REPRODUCTION_STRATEGIES),
                    ("exploration_strategy", EXPLORATION_STRATEGIES),
                    ("energy_strategy", ENERGY_STRATEGIES),
                    ("memory_bias", MEMORY_BIASES),
                ]
            )
            values[field_name] = _neighbor_enum(str(values[field_name]), options, rng)
        values["model_deliberation_bias"] = clamp(policy.model_deliberation_bias + rng.gauss(0.0, 0.025), -0.22, 0.22)
        values["risk_bias"] = clamp(policy.risk_bias + rng.gauss(0.0, 0.022), -0.22, 0.22)
        values["energy_bias"] = clamp(policy.energy_bias + rng.gauss(0.0, 0.018), -0.22, 0.22)
        if rng.random() < rate * 0.45:
            values["allowed_skill_slots"] = max(0, min(4, int(policy.allowed_skill_slots) + rng.choice([-1, 1])))
        values["policy_id"] = _short(
            f"{values['risk_posture']}-{values['forage_strategy']}-{values['energy_strategy']}",
            48,
        )
        values["inherited_from_policy_hash"] = parent_hash or policy.policy_hash
        return BehaviorInstructionGenome(**values).normalized()

    def with_patch_result(self, patch_id: str, *, accepted: bool) -> "BehaviorInstructionGenome":
        values = self.__dict__.copy()
        if accepted:
            values["accepted_patch_ids"] = (*self.accepted_patch_ids, _short(patch_id, 32))[-8:]
        else:
            values["rejected_patch_ids"] = (*self.rejected_patch_ids, _short(patch_id, 32))[-8:]
        return BehaviorInstructionGenome(**values).normalized()

    def with_skill_bias(self, skill: TaughtSkill) -> "BehaviorInstructionGenome":
        values = self.__dict__.copy()
        if skill.skill_type == "forage" and skill.action_bias in FORAGE_STRATEGIES:
            values["forage_strategy"] = skill.action_bias
        elif skill.skill_type == "threat" and skill.action_bias in THREAT_STRATEGIES:
            values["threat_strategy"] = skill.action_bias
        elif skill.skill_type == "social" and skill.action_bias in SOCIAL_STRATEGIES:
            values["social_strategy"] = skill.action_bias
        elif skill.skill_type == "explore" and skill.action_bias in EXPLORATION_STRATEGIES:
            values["exploration_strategy"] = skill.action_bias
        elif skill.skill_type == "reproduce" and skill.action_bias in REPRODUCTION_STRATEGIES:
            values["reproduction_strategy"] = skill.action_bias
        elif skill.skill_type == "energy" and skill.action_bias in ENERGY_STRATEGIES:
            values["energy_strategy"] = skill.action_bias
        values["memory_bias"] = skill.memory_bias if skill.memory_bias in MEMORY_BIASES else self.memory_bias
        values["risk_bias"] = clamp(self.risk_bias + skill.risk_bias * 0.35, -0.22, 0.22)
        values["energy_bias"] = clamp(self.energy_bias + skill.energy_cost_bias * 0.25, -0.22, 0.22)
        return BehaviorInstructionGenome(**values).normalized()


@dataclass(frozen=True)
class InstructionPatchDecision:
    accepted: bool
    reason: str
    patch_id: str
    skill: TaughtSkill | None = None
    sanitized_patch: dict[str, Any] | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "patch_id": self.patch_id,
            "skill": self.skill.payload(compact=True) if self.skill else None,
            "sanitized_patch": self.sanitized_patch,
        }


def validate_instruction_genome(genome: BehaviorInstructionGenome) -> BehaviorInstructionGenome:
    normalized = genome.normalized()
    if normalized.policy_payload(include_hash=False) != genome.normalized().policy_payload(include_hash=False):
        return normalized
    return normalized


def validate_taught_skill(skill: TaughtSkill) -> TaughtSkill:
    if skill.skill_type not in SKILL_TYPES:
        raise ValueError("invalid skill_type")
    if skill.skill_type not in ACTION_BIASES or skill.action_bias not in ACTION_BIASES[skill.skill_type]:
        raise ValueError("invalid action_bias")
    if skill.memory_bias not in MEMORY_BIASES:
        raise ValueError("invalid memory_bias")
    for value in (skill.trigger, skill.rationale_tag):
        _reject_forbidden_text(value)
    if len(skill.trigger) > 64 or len(skill.rationale_tag) > 64:
        raise ValueError("skill text exceeds bounded length")
    return TaughtSkill(
        skill_id=_short(skill.skill_id, 32) or skill.skill_hash,
        source_parent_id=max(0, int(skill.source_parent_id)),
        source_lineage_id=max(0, int(skill.source_lineage_id)),
        created_tick=max(0, int(skill.created_tick)),
        generation_created=max(0, int(skill.generation_created)),
        skill_type=skill.skill_type,
        trigger=_short(skill.trigger, 64),
        action_bias=skill.action_bias,
        confidence=clamp(skill.confidence),
        energy_cost_bias=clamp(skill.energy_cost_bias, -0.22, 0.22),
        risk_bias=clamp(skill.risk_bias, -0.22, 0.22),
        memory_bias=skill.memory_bias,
        ttl_generations=max(1, min(5, int(skill.ttl_generations))),
        decay=clamp(skill.decay, 0.05, 0.85),
        rationale_tag=_short(skill.rationale_tag, 64),
        patch_id=_short(skill.patch_id, 32),
    )


def inherit_taught_skills(
    parent_skills: list[TaughtSkill],
    *,
    current_generation: int,
    allowed_slots: int,
    rng: Random,
) -> list[TaughtSkill]:
    inherited: list[TaughtSkill] = []
    for skill in parent_skills:
        if skill.expired_for_generation(current_generation):
            continue
        if rng.random() > clamp(skill.confidence * (1.0 - skill.decay * 0.35), 0.08, 0.92):
            continue
        inherited.append(skill)
    inherited.sort(key=lambda item: (item.confidence, -item.created_tick), reverse=True)
    return inherited[: max(0, allowed_slots)]


def rule_generated_patch(parent: Any, *, tick: int, lineage_population: int, adult_population: int) -> dict[str, Any] | None:
    instruction = parent.instruction_genome
    recent = parent.memory.summary()
    outcomes = {name: count for name, count in recent.get("common_outcomes", [])}
    if outcomes.get("fed", 0) >= 2 and instruction.teaching_style in {"conservative", "opportunistic"}:
        return {
            "patch_type": "offspring_behavior_prior",
            "target_skill_type": "forage",
            "trigger": "low_energy",
            "action_bias": "safe_food" if instruction.risk_posture == "cautious" else instruction.forage_strategy,
            "risk_delta": -0.06 if instruction.risk_posture == "cautious" else 0.02,
            "energy_bias": "conserve" if instruction.energy_strategy == "conserve" else "balanced",
            "memory_bias": "prefer_energy_gain",
            "ttl_generations": 2,
            "rationale_tag": "parent_recent_feeding_success",
        }
    if outcomes.get("sheltered", 0) >= 2 or parent.fear > 0.62:
        return {
            "patch_type": "offspring_behavior_prior",
            "target_skill_type": "threat",
            "trigger": "high_fear",
            "action_bias": "hide",
            "risk_delta": -0.10,
            "energy_bias": "conserve",
            "memory_bias": "prefer_safe_outcomes",
            "ttl_generations": 3,
            "rationale_tag": "parent_survived_by_shelter",
        }
    if lineage_population <= 2 or adult_population <= 5:
        return {
            "patch_type": "offspring_behavior_prior",
            "target_skill_type": "reproduce",
            "trigger": "lineage_bottleneck",
            "action_bias": "emergency_last_chance",
            "risk_delta": -0.02,
            "energy_bias": "balanced",
            "memory_bias": "prefer_recent_success",
            "ttl_generations": 2,
            "rationale_tag": "lineage_bottleneck",
        }
    if parent.energy > 70.0 and instruction.exploration_strategy == "novelty_seek":
        return {
            "patch_type": "offspring_behavior_prior",
            "target_skill_type": "explore",
            "trigger": "high_energy",
            "action_bias": "novelty_seek",
            "risk_delta": 0.06,
            "energy_bias": "burst_then_recover",
            "memory_bias": "prefer_recent_success",
            "ttl_generations": 2,
            "rationale_tag": "parent_high_energy_exploration",
        }
    return None


def validate_instruction_patch(
    payload: dict[str, Any],
    *,
    parent_id: int,
    lineage_id: int,
    generation: int,
    created_tick: int,
    allowed_skill_slots: int,
) -> InstructionPatchDecision:
    patch_id = stable_hash({"parent_id": parent_id, "tick": created_tick, "payload": payload}, length=16)
    if not isinstance(payload, dict):
        return InstructionPatchDecision(False, "patch_not_object", patch_id)
    if len(canonical_json(payload)) > 900:
        return InstructionPatchDecision(False, "complexity_cap_exceeded", patch_id)
    for key, value in payload.items():
        if key not in {
            "patch_type",
            "target_skill_type",
            "trigger",
            "action_bias",
            "risk_delta",
            "energy_bias",
            "memory_bias",
            "ttl_generations",
            "rationale_tag",
        }:
            return InstructionPatchDecision(False, "unknown_field", patch_id)
        if isinstance(value, str):
            try:
                _reject_forbidden_text(value)
            except ValueError as exc:
                return InstructionPatchDecision(False, str(exc), patch_id)
    if allowed_skill_slots <= 0:
        return InstructionPatchDecision(False, "skill_slot_cap_exceeded", patch_id)
    if payload.get("patch_type") not in PATCH_TYPES:
        return InstructionPatchDecision(False, "invalid_patch_type", patch_id)
    skill_type = str(payload.get("target_skill_type", "")).strip().lower()
    if skill_type not in SKILL_TYPES:
        return InstructionPatchDecision(False, "invalid_skill_type", patch_id)
    action_bias = str(payload.get("action_bias", "")).strip().lower()
    if action_bias not in ACTION_BIASES[skill_type]:
        return InstructionPatchDecision(False, "invalid_action_bias", patch_id)
    trigger = _short(payload.get("trigger", ""), 64)
    rationale = _short(payload.get("rationale_tag", ""), 64)
    if not trigger:
        return InstructionPatchDecision(False, "missing_trigger", patch_id)
    if len(str(payload.get("trigger", ""))) > 64 or len(str(payload.get("rationale_tag", ""))) > 64:
        return InstructionPatchDecision(False, "bounded_text_exceeded", patch_id)
    memory_bias = str(payload.get("memory_bias", "prefer_recent_success")).strip().lower()
    if memory_bias not in MEMORY_BIASES:
        return InstructionPatchDecision(False, "invalid_memory_bias", patch_id)
    energy_bias_raw = str(payload.get("energy_bias", "balanced")).strip().lower()
    energy_cost_bias = {"conserve": -0.08, "balanced": 0.0, "burst_then_recover": 0.08}.get(energy_bias_raw)
    if energy_cost_bias is None:
        return InstructionPatchDecision(False, "invalid_energy_bias", patch_id)
    try:
        risk_bias = float(payload.get("risk_delta", 0.0))
    except (TypeError, ValueError):
        return InstructionPatchDecision(False, "invalid_risk_delta", patch_id)
    try:
        ttl = int(payload.get("ttl_generations", 2))
    except (TypeError, ValueError):
        return InstructionPatchDecision(False, "invalid_ttl", patch_id)
    skill = validate_taught_skill(
        TaughtSkill(
            skill_id=f"skill-{patch_id[:8]}",
            source_parent_id=parent_id,
            source_lineage_id=lineage_id,
            created_tick=created_tick,
            generation_created=generation,
            skill_type=skill_type,
            trigger=trigger,
            action_bias=action_bias,
            confidence=0.58,
            energy_cost_bias=energy_cost_bias,
            risk_bias=risk_bias,
            memory_bias=memory_bias,
            ttl_generations=ttl,
            decay=0.24,
            rationale_tag=rationale,
            patch_id=patch_id,
        )
    )
    return InstructionPatchDecision(
        True,
        "accepted",
        patch_id,
        skill=skill,
        sanitized_patch={
            "patch_type": "offspring_behavior_prior",
            "target_skill_type": skill.skill_type,
            "trigger": skill.trigger,
            "action_bias": skill.action_bias,
            "risk_delta": round(skill.risk_bias, 3),
            "energy_bias": energy_bias_raw,
            "memory_bias": skill.memory_bias,
            "ttl_generations": skill.ttl_generations,
            "rationale_tag": skill.rationale_tag,
        },
    )


def _reject_forbidden_text(value: object) -> None:
    text = str(value or "").strip().lower()
    for token in FORBIDDEN_TOKENS:
        if token in text:
            raise ValueError(f"forbidden_capability:{token.replace(' ', '_')}")
