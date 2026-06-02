from __future__ import annotations

from dataclasses import dataclass
from random import Random

RANKS = "23456789TJQKA"
SUITS = "CDHS"
RANK_VALUE = {rank: index + 2 for index, rank in enumerate(RANKS)}


@dataclass(frozen=True, order=True)
class Card:
    rank: str
    suit: str

    @property
    def value(self) -> int:
        return RANK_VALUE[self.rank]

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    @classmethod
    def parse(cls, text: str) -> "Card":
        text = text.strip().upper()
        if len(text) != 2 or text[0] not in RANKS or text[1] not in SUITS:
            raise ValueError(f"invalid card: {text!r}")
        return cls(text[0], text[1])


def new_deck(seed: int | None = None) -> list[Card]:
    deck = [Card(rank, suit) for suit in SUITS for rank in RANKS]
    Random(seed).shuffle(deck)
    return deck


def cards_from_text(items: list[str]) -> list[Card]:
    return [Card.parse(item) for item in items]
