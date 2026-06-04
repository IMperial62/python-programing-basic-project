import unittest

from holdem.cards import cards_from_text
from holdem.evaluator import best_score


class EvaluatorTest(unittest.TestCase):
    def test_straight_flush_beats_quads(self):
        straight_flush = cards_from_text(["AS", "KS", "QS", "JS", "TS", "2C", "3D"])
        quads = cards_from_text(["9S", "9H", "9D", "9C", "AS", "2C", "3D"])
        self.assertGreater(best_score(straight_flush), best_score(quads))

    def test_wheel_straight(self):
        cards = cards_from_text(["AS", "2H", "3D", "4C", "5S", "9C", "TD"])
        self.assertEqual(best_score(cards), (4, 5))


if __name__ == "__main__":
    unittest.main()
