from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Expression:
    value: float
    cost: float
    load: float
    deficit: float
    excess: float
    state: str


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def copy_count_expression(
    count: int,
    *,
    optimum: int,
    high: int,
    extreme: int,
    base_cost: float = 0.03,
    essential: bool = False,
) -> Expression:
    if count <= 0:
        load = 0.12 if essential else 0.0
        return Expression(0.0, 0.0, load, 1.0 if essential else 0.0, 0.0, "absent")

    if count < optimum:
        ratio = count / max(1, optimum)
        deficit = 1.0 - ratio
        load = deficit * (0.10 if essential else 0.025)
        return Expression(0.68 * ratio, base_cost * count * 0.45, load, deficit, 0.0, "deficit")

    if count <= high:
        span = max(1, high - optimum)
        ratio = (count - optimum) / span
        value = 0.68 + 0.38 * ratio
        cost = base_cost * (count / max(1, optimum)) ** 1.12
        return Expression(value, cost, 0.0, 0.0, 0.0, "viable")

    if count <= extreme:
        span = max(1, extreme - high)
        excess = (count - high) / span
        value = 1.06 + 0.35 * excess
        cost = base_cost * (count / max(1, optimum)) ** 1.45
        load = 0.05 + 0.22 * excess
        return Expression(value, cost, load, 0.0, excess, "overexpressed")

    excess = min(2.0, (count - extreme) / max(1, extreme))
    cost = base_cost * (count / max(1, optimum)) ** 1.8
    return Expression(1.42, cost, 0.32 + 0.35 * excess, 0.0, 1.0 + excess, "extreme")
