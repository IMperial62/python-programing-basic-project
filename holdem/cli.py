from __future__ import annotations

from .game import Table


def cards(items) -> str:
    return " ".join(map(str, items)) or "-"


def ask(text: str) -> str:
    try:
        return input(text)
    except EOFError:
        return "q"


def render(table: Table) -> None:
    print("\n" + "=" * 72)
    print(f"Hand {table.hand_no} | Stage: {table.stage} | Pot: {table.pot} | Current bet: {table.current_bet}")
    print(f"Board: {cards(table.board)}")
    print("-" * 72)
    for i, player in enumerate(table.players):
        marker = "▶" if table.stage != "showdown" and i == table.current_player else " "
        hand = cards(player.hand) if player.is_human or table.stage == "showdown" else "?? ??"
        state = "fold" if player.folded else "all-in" if player.all_in else "play"
        win = " 🏆" if player.id in table.winner_ids else ""
        print(f"{marker} {player.name:<8} chips={player.chips:<4} bet={player.bet:<4} {state:<6} hand={hand}{win}")
    print("-" * 72)
    for line in table.action_log[-6:]:
        print("·", line)


def choose_human_action(table: Table) -> tuple[str, int]:
    actions = table.legal_actions()
    while True:
        raw = ask(f"Action {actions} (raise/bet 금액 예: raise 40, q=종료): ").strip().lower()
        if raw == "q":
            raise SystemExit(0)
        if not raw:
            raw = "check" if "check" in actions else "call"
        parts = raw.split()
        action = parts[0]
        if action not in actions:
            print("지금 가능한 액션이 아닙니다.")
            continue
        amount = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else table.big_blind
        return action, amount


def main() -> None:
    seats_text = ask("플레이어 수(2-6, 기본 4): ").strip()
    if seats_text.lower() == "q":
        return
    seats = int(seats_text) if seats_text.isdigit() else 4
    table = Table.create(seats=seats)

    while True:
        render(table)
        if table.stage == "showdown":
            cmd = ask("Enter=새 핸드, q=종료: ").strip().lower()
            if cmd == "q":
                break
            table.start_hand()
            continue

        actor = table.actor
        if actor.is_human:
            action, amount = choose_human_action(table)
            table.apply_action(actor.id, action, amount)
        else:
            cmd = ask(f"{actor.name} 차례입니다. Enter=봇 한 턴, q=종료: ").strip().lower()
            if cmd == "q":
                break
            table.play_bot_turn()


if __name__ == "__main__":
    main()
