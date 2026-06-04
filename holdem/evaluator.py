from __future__ import annotations

from collections import Counter
from itertools import combinations

from .cards import Card

# Larger tuples are stronger. Category: 8 straight flush ... 0 high card.
Score = tuple[int, ...]


def _straight_high(values: list[int]) -> int | None:
    unique = sorted(set(values), reverse=True)
    if 14 in unique:
        unique.append(1)  # wheel straight: A-2-3-4-5
    for window in (unique[i : i + 5] for i in range(len(unique) - 4)):
        if window[0] - window[4] == 4 and len(set(window)) == 5:
            return 5 if window[0] == 5 else window[0]
    return None


def score_five(cards: list[Card]) -> Score:
    values = sorted((card.value for card in cards), reverse=True)
    counts = Counter(values)
    groups = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    flush = len({card.suit for card in cards}) == 1
    straight = _straight_high(values)

    if flush and straight:
        return (8, straight)
    if groups[0][1] == 4:
        quad = groups[0][0]
        kicker = max(value for value in values if value != quad)
        return (7, quad, kicker)
    if groups[0][1] == 3 and groups[1][1] == 2:
        return (6, groups[0][0], groups[1][0])
    if flush:
        return (5, *values)
    if straight:
        return (4, straight)
    if groups[0][1] == 3:
        trips = groups[0][0]
        kickers = [value for value in values if value != trips]
        return (3, trips, *kickers)
    if groups[0][1] == 2 and groups[1][1] == 2:
        high_pair, low_pair = sorted([groups[0][0], groups[1][0]], reverse=True)
        kicker = max(value for value in values if value not in (high_pair, low_pair))
        return (2, high_pair, low_pair, kicker)
    if groups[0][1] == 2:
        pair = groups[0][0]
        kickers = [value for value in values if value != pair]
        return (1, pair, *kickers)
    return (0, *values)


def best_score(cards: list[Card]) -> Score:
    if len(cards) < 5:
        raise ValueError("at least five cards are required")
    return max(score_five(list(combo)) for combo in combinations(cards, 5))


def compare(left: list[Card], right: list[Card]) -> int:
    return (best_score(left) > best_score(right)) - (best_score(left) < best_score(right))
