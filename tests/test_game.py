import tempfile
import unittest

from holdem.game import Table
from holdem.store import Store


class GameTest(unittest.TestCase):
    def test_table_starts_preflop_with_hole_cards(self):
        table = Table.create(seats=3)
        self.assertEqual(table.stage, "preflop")
        self.assertEqual(len(table.players[0].hand), 2)
        self.assertEqual(table.pot, table.small_blind + table.big_blind)

    def test_basic_actions_reach_terminal_state(self):
        table = Table.create(seats=3)
        guard = 0
        while table.stage != "showdown" and guard < 80:
            player = table.players[table.current_player]
            to_call = table.current_bet - player.bet
            action = "call" if to_call else "check"
            table.apply_action(player.id, action)
            guard += 1
        self.assertEqual(table.stage, "showdown")
        self.assertTrue(table.winner_ids)

    def test_human_action_stops_on_next_bot_without_auto_skipping(self):
        table = Table.create(seats=3)
        self.assertTrue(table.actor.is_human)
        first = table.current_player
        table.apply_action(table.actor.id, "call")
        self.assertNotEqual(table.current_player, first)
        self.assertFalse(table.actor.is_human)

    def test_bot_takes_one_valid_turn(self):
        table = Table.create(seats=3)
        table.current_player = 1
        visible = table.visible_state()
        self.assertGreaterEqual(visible["bot_delay_ms"], 1000)
        self.assertLessEqual(visible["bot_delay_ms"], 5000)
        self.assertIn("strength", visible["bot_thought"])
        self.assertIn("pressure", visible["bot_thought"])
        self.assertIn("roll", visible["bot_thought"])
        before_log = len(table.action_log)
        action, amount = table.play_bot_turn()
        self.assertIn(action, {"check", "call", "fold", "bet", "raise"})
        self.assertGreaterEqual(amount, 0)
        self.assertGreater(len(table.action_log), before_log)
        self.assertEqual(table.last_action["player_id"], "p2")
        self.assertIn(table.last_action["action"], {"check", "call", "fold", "bet", "raise"})
        self.assertIn("speech", table.last_action)
        self.assertIn("street_bet", table.last_action)

    def test_showdown_exposes_rank_and_reveal_timing(self):
        table = Table.create(seats=3)
        guard = 0
        while table.stage != "showdown" and guard < 80:
            player = table.players[table.current_player]
            to_call = table.current_bet - player.bet
            table.apply_action(player.id, "call" if to_call else "check")
            guard += 1
        state = table.visible_state()
        self.assertTrue(state["showdown"])
        for row in state["showdown"]:
            self.assertIn(row["tier"], {"weak", "solid", "strong", "monster"})
            self.assertGreaterEqual(row["reveal_ms"], 1050)
            self.assertLessEqual(row["reveal_ms"], 2570)
            self.assertIn(row["label"], {
                "High Card", "One Pair", "Two Pair", "Trips", "Straight",
                "Flush", "Full House", "Quads", "Straight Flush",
            })

    def test_bot_endpoint_style_action_not_required_for_human_turn(self):
        table = Table.create(seats=4)
        if table.actor.is_human:
            table.apply_action(table.actor.id, "call")
        self.assertFalse(table.actor.is_human)
        before = table.current_player
        table.play_bot_turn()
        self.assertNotEqual(table.current_player, before)

    def test_split_pot_conserves_odd_chip(self):
        table = Table.create(seats=2)
        table.pot = 5
        table.players[0].chips = 10
        table.players[1].chips = 20
        table._award(table.players, "Tie.")
        self.assertEqual(table.pot, 0)
        self.assertEqual(sum(player.chips for player in table.players), 35)
        self.assertEqual([player.chips for player in table.players], [13, 22])

    def test_store_round_trip(self):
        table = Table.create(seats=2)
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(f"{tmp}/holdem.sqlite")
            store.save(table)
            loaded = store.load(table.id)
        self.assertEqual(loaded.to_dict(), table.to_dict())


if __name__ == "__main__":
    unittest.main()
