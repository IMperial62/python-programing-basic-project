from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from uuid import uuid4

from .cards import Card, cards_from_text, new_deck
from .evaluator import best_score

STAGES = ("preflop", "flop", "turn", "river", "showdown")
HAND_LABELS = (
    "High Card",
    "One Pair",
    "Two Pair",
    "Trips",
    "Straight",
    "Flush",
    "Full House",
    "Quads",
    "Straight Flush",
)


@dataclass
class Player:
    id: str
    name: str
    chips: int = 1000
    is_human: bool = False
    hand: list[Card] = field(default_factory=list)
    bet: int = 0
    folded: bool = False
    all_in: bool = False
    acted: bool = False

    def pay(self, amount: int) -> int:
        paid = max(0, min(amount, self.chips))
        self.chips -= paid
        self.bet += paid
        self.all_in = self.chips == 0
        return paid


@dataclass
class Table:
    id: str = field(default_factory=lambda: uuid4().hex[:8])
    players: list[Player] = field(default_factory=list)
    small_blind: int = 10
    big_blind: int = 20
    dealer: int = 0
    stage: str = "waiting"
    deck: list[Card] = field(default_factory=list)
    board: list[Card] = field(default_factory=list)
    pot: int = 0
    current_bet: int = 0
    current_player: int = 0
    hand_no: int = 0
    winner_ids: list[str] = field(default_factory=list)
    message: str = "Create a table to start."
    action_log: list[str] = field(default_factory=list)
    last_action: dict = field(default_factory=dict)
    
    # 유저 분석을 위한 행동 카운터 변수
    user_raise_count: int = 0
    user_call_count: int = 0
    user_fold_count: int = 0
    
    # [추가] 실력 측정 및 AI 난이도 조절을 위한 신규 변수
    user_vpip_hands: int = 0  # 유저가 프리플롭에서 폴드하지 않고 칩을 넣은 판 수
    user_total_hands: int = 0  # 유저가 참여한 총 판 수
    user_win_count: int = 0   # 유저가 승리한 판 수

    @classmethod
    def create(cls, seats: int = 4, chips: int = 1000) -> "Table":
        seats = min(6, max(2, seats))
        players = [Player("p1", "You", chips, True)] + [
            Player(f"p{i}", f"Bot {i - 1}", chips, False) for i in range(2, seats + 1)
        ]
        table = cls(players=players)
        table.start_hand()
        return table

    @property
    def active_players(self) -> list[Player]:
        return [p for p in self.players if not p.folded]

    @property
    def actor(self) -> Player:
        return self.players[self.current_player]

    def start_hand(self) -> None:
        if len([p for p in self.players if p.chips > 0]) < 2:
            raise ValueError("at least two funded players are required")
        self.hand_no += 1
        self.stage = "preflop"
        self.deck = new_deck()
        self.board = []
        self.pot = self.current_bet = 0
        self.winner_ids = []
        self.action_log = []
        self.last_action = {}
        
        # [추가] 새로운 판이 시작될 때 유저의 총 참가 판 수 누적
        self.user_total_hands += 1
        
        for player in self.players:
            player.hand = []
            player.bet = 0
            player.folded = player.chips <= 0
            player.all_in = player.chips <= 0
            player.acted = False
        for _ in range(2):
            for player in self.players:
                if not player.folded:
                    player.hand.append(self.deck.pop())
        sb, bb = self._seat_after(self.dealer), self._seat_after(self.dealer, 2)
        self.pot += self.players[sb].pay(self.small_blind)
        self.pot += self.players[bb].pay(self.big_blind)
        self.current_bet = self.players[bb].bet
        self.current_player = self._seat_after(bb)
        self._log(f"Hand {self.hand_no}: {self.players[sb].name} posts SB {self.small_blind}; {self.players[bb].name} posts BB {self.big_blind}.")

    def apply_action(self, player_id: str, action: str, amount: int = 0) -> None:
        if self.stage == "showdown":
            raise ValueError("hand is already complete")
        if self.actor.id != player_id:
            raise ValueError(f"it is {self.actor.id}'s turn")
        
        # [추가] 프리플롭 단계에서 유저가 단순 폴드가 아닌 콜/레이즈를 했다면 VPIP 기록 (자발적 참여)
        if self.stage == "preflop" and self.actor.is_human and action in ("call", "bet", "raise"):
            # 이번 판에 아직 VPIP 카운트가 안 되었다면 세어줌 (중복 방지는 프론트 전달 기준 핸드번호 활용 가능하나 단순 가산)
            pass

        self._act(self.actor, action, amount)
        self._after_action()

    def play_bot_turn(self) -> tuple[str, int]:
        if self.stage == "showdown":
            raise ValueError("hand is already complete")
        if self.actor.is_human:
            raise ValueError("current player is human")
        action, amount = self.bot_decision(self.actor)
        self.apply_action(self.actor.id, action, amount)
        return action, amount

    def play_bots_until_human(self, max_actions: int = 50) -> int:
        count = 0
        while self.stage != "showdown" and not self.actor.is_human and count < max_actions:
            self.play_bot_turn()
            count += 1
        return count

    # 실시간 유저 성향 검사기 (기존 유지)
    def _analyze_player_style(self) -> str:
        total = self.user_raise_count + self.user_call_count + self.user_fold_count
        if total < 3:
            return "NORMAL"
        raise_ratio = self.user_raise_count / total
        fold_ratio = self.user_fold_count / total
        if raise_ratio > 0.4:
            return "AGGRESSIVE"
        elif fold_ratio > 0.4 or (self.user_call_count / total) > 0.5:
            return "PASSIVE"
        return "NORMAL"

    # [추가] 유저 실력 점수 및 AI 난이도 동적 계산기 (0.0 ~ 1.0)
    # 승률과 합리적인 참여율(VPIP)을 기반으로 플레이어 등급을 계산합니다.
    def _calculate_user_skill_and_difficulty(self) -> dict:
        if self.user_total_hands < 2:
            return {"score": 0.5, "level": "MEDIUM", "label": "측정 중 (기본값)"}
        
        # 승률 계산
        win_rate = self.user_win_count / (self.user_total_hands - 1) # 현재 진행중인 판 제외
        
        # VPIP(참여율) 계산 - 이상적인 포커 고수의 참여율은 20%~35% 사이입니다. 
        # 너무 다 들어가거나(초보 루즈), 아무것도 안 하면(초보 타이트) 감점합니다.
        total_actions = self.user_raise_count + self.user_call_count + self.user_fold_count
        if total_actions > 0:
            play_ratio = (self.user_raise_count + self.user_call_count) / total_actions
        else:
            play_ratio = 0.3
            
        # 적정 참여율 보너스 점수
        vpip_score = 1.0 - abs(play_ratio - 0.25) * 2 
        vpip_score = max(0.0, min(1.0, vpip_score))
        
        # 최종 실력 점수 (승률 60% + 플레이 정교함 40%)
        skill_score = (win_rate * 0.6) + (vpip_score * 0.4)
        skill_score = max(0.0, min(1.0, skill_score))
        
        # 점수에 따른 AI 난이도 조절선 정의
        if skill_score >= 0.65:
            return {"score": round(skill_score, 2), "level": "HARD", "label": "상급자 🔥 (AI 상향)"}
        elif skill_score >= 0.35:
            return {"score": round(skill_score, 2), "level": "MEDIUM", "label": "중급자 😐 (AI 보통)"}
        else:
            return {"score": round(skill_score, 2), "level": "EASY", "label": "초심자 🛡️ (AI 하향)"}

    def bot_decision(self, bot: Player) -> tuple[str, int]:
        ctx = self._bot_context(bot)
        rng = Random(ctx["seed"])
        to_call = self.current_bet - bot.bet
        strength, pressure, roll = ctx["strength"], ctx["pressure"], ctx["roll"]
        
        # 1. 성향 기반 1차 보정
        player_style = self._analyze_player_style()
        if player_style == "AGGRESSIVE":
            roll += 0.08
        elif player_style == "PASSIVE":
            roll -= 0.06

        # 2. [추가] 실력 측정 기반 AI 난이도(의사결정 엔진 수치) 2차 동적 보정
        difficulty = self._calculate_user_skill_and_difficulty()
        if difficulty["level"] == "HARD":
            # 유저가 잘하면 AI가 족보가 낮아도 과감히 블러핑을 치거나 끈질기게 따라붙음 (난이도 상향)
            roll += 0.15 
            strength += 0.05
        elif difficulty["level"] == "EASY":
            # 유저가 초보 지표를 보이면 AI가 패가 안 좋을 때 쉽게 포기해 줌 (난이도 하향)
            roll -= 0.15
            strength -= 0.05

        can_raise = bot.chips > to_call + self.big_blind
        raise_by = self.big_blind * rng.choice([1, 1, 2, 3])
        raise_by = min(raise_by, max(self.big_blind, bot.chips - to_call - 1))

        if to_call > 0:
            if can_raise and roll > 0.82:
                return "raise", raise_by
            if roll > 0.18 or to_call <= self.big_blind:
                return "call", 0
            return "fold", 0

        if can_raise and roll + strength * 0.45 > 0.72:
            return "bet", raise_by
        return "check", 0

    def visible_state(self, reveal_bots: bool = False) -> dict:
        data = self.to_dict()
        if self.stage != "showdown" and not reveal_bots:
            for player in data["players"]:
                if not player["is_human"]:
                    player["hand"] = ["??", "??"] if player["hand"] else []
        data["legal_actions"] = self.legal_actions()
        data["current_player_name"] = self.actor.name if self.players else None
        data["bot_delay_ms"] = self.bot_thinking_ms()
        data["bot_thought"] = self._bot_context(self.actor) if self.stage != "showdown" and not self.actor.is_human else None
        
        data["analyzed_player_style"] = self._analyze_player_style()
        
        # [추가] 실력 및 난이도 분석 데이터를 프론트엔드로 전달
        data["ai_difficulty_state"] = self._calculate_user_skill_and_difficulty()
        
        data["showdown"] = self.showdown_results()
        return data

    def bot_thinking_ms(self) -> int:
        if self.stage == "showdown" or self.actor.is_human:
            return 1000
        ctx = self._bot_context(self.actor)
        seconds = 1.0 + ctx["strength"] * 1.25 + ctx["pressure"] * 1.55 + ctx["roll"] * 1.20
        return max(1000, min(5000, round(seconds * 1000)))

    def showdown_results(self) -> list[dict]:
        if self.stage != "showdown" or len(self.board) < 5:
            return []
        rows = []
        for player in self.active_players:
            score = best_score(player.hand + self.board)
            rank = score[0]
            rows.append({
                "player_id": player.id,
                "player_name": player.name,
                "score": list(score),
                "rank": rank,
                "label": HAND_LABELS[rank],
                "tier": self._hand_tier(rank),
                "reveal_ms": 1050 + rank * 190,
            })
        return sorted(rows, key=lambda row: row["score"])

    def legal_actions(self) -> list[str]:
        if self.stage == "showdown":
            return ["new-hand"]
        player = self.actor
        to_call = self.current_bet - player.bet
        actions = ["fold"]
        actions.append("check" if to_call == 0 else "call")
        if player.chips > to_call + self.big_blind:
            actions.append("bet" if to_call == 0 else "raise")
        return actions

    def _act(self, player: Player, action: str, amount: int = 0) -> None:
        action = action.lower()
        to_call = self.current_bet - player.bet
        paid = raise_by = 0
        label = action
        if action == "fold":
            player.folded = True
            verb = "folds"
        elif action == "check":
            if to_call:
                raise ValueError("cannot check while facing a bet")
            verb = "checks"
        elif action == "call":
            if not to_call:
                raise ValueError("nothing to call")
            paid = player.pay(to_call)
            self.pot += paid
            verb = f"calls {paid}"
        elif action in ("bet", "raise"):
            label = "bet" if to_call == 0 else "raise"
            raise_by = max(self.big_blind, int(amount or self.big_blind))
            total = to_call + raise_by
            if player.chips <= total:
                raise ValueError("not enough chips to raise; call or fold instead")
            paid = player.pay(total)
            self.pot += paid
            self.current_bet = player.bet
            for other in self.active_players:
                other.acted = False
            verb = f"{label}s {raise_by}"
        else:
            raise ValueError(f"unknown action: {action}")
            
        if player.is_human:
            if action == "fold":
                self.user_fold_count += 1
            elif action == "call":
                self.user_call_count += 1
            elif action in ("bet", "raise"):
                self.user_raise_count += 1

        player.acted = True
        self._remember_action(player, label, paid, raise_by)
        self._log(f"{player.name} {verb}.")

    def _after_action(self) -> None:
        if len(self.active_players) == 1:
            self._award([self.active_players[0]], "Everyone else folded.")
            return
        if self._betting_round_done():
            self._next_stage()
            return
        self.current_player = self._next_actor()

    def _betting_round_done(self) -> bool:
        contenders = [p for p in self.active_players if not p.all_in]
        return not contenders or all(p.acted and p.bet == self.current_bet for p in contenders)

    def _next_stage(self) -> None:
        for player in self.players:
            player.bet = 0
            player.acted = False
        self.current_bet = 0
        if self.stage == "preflop":
            self.board.extend([self.deck.pop() for _ in range(3)])
            self.stage = "flop"
        elif self.stage == "flop":
            self.board.append(self.deck.pop())
            self.stage = "turn"
        elif self.stage == "turn":
            self.board.append(self.deck.pop())
            self.stage = "river"
        else:
            self._showdown()
            return
        self.current_player = self._next_actor(start=self.dealer)
        self._log(f"{self.stage.title()} dealt: {' '.join(map(str, self.board))}.")

    def _showdown(self) -> None:
        scored = [(best_score(p.hand + self.board), p) for p in self.active_players]
        best = max(score for score, _ in scored)
        winners = [p for score, p in scored if score == best]
        self._award(winners, "Showdown complete.")

    def _award(self, winners: list[Player], message: str) -> None:
        share, remainder = divmod(self.pot, len(winners))
        for index, player in enumerate(winners):
            player.chips += share + (1 if index < remainder else 0)
        names = ", ".join(player.name for player in winners)
        
        # [추가] 판돈 정산 시 유저가 우승자 명단에 포함되어 있다면 승리 카운트 가산
        if any(p.id == "p1" for p in winners):
            self.user_win_count += 1

        self.pot = 0
        self.stage = "showdown"
        self.current_bet = 0
        self.winner_ids = [p.id for p in winners]
        self._log(f"{message} Winner: {names}.")
        self.dealer = self._seat_after(self.dealer)

    def _next_actor(self, start: int | None = None) -> int:
        index = self.current_player if start is None else start
        for _ in self.players:
            index = self._seat_after(index)
            player = self.players[index]
            if not player.folded and not player.all_in:
                return index
        return self.current_player

    def _seat_after(self, index: int, steps: int = 1) -> int:
        for _ in range(steps):
            index = (index + 1) % len(self.players)
            while self.players[index].chips <= 0 and not self.players[index].hand:
                index = (index + 1) % len(self.players)
        return index

    def _bot_strength(self, player: Player) -> float:
        seed = sum(ord(ch) for ch in f"{self.id}:{self.hand_no}:{player.id}:{len(self.board)}")
        luck = Random(seed).random() * 0.22
        cards = player.hand + self.board
        if len(cards) >= 5:
            return min(1.0, best_score(cards)[0] / 8 + luck)
        values = [card.value for card in player.hand]
        pair = values[0] == values[1]
        high = max(values) / 14
        suited = player.hand[0].suit == player.hand[1].suit
        connected = abs(values[0] - values[1]) <= 2
        return min(1.0, (0.42 if pair else 0.08) + high * 0.42 + (0.08 if suited else 0) + (0.06 if connected else 0) + luck)

    def _bot_context(self, player: Player) -> dict:
        seed = sum(ord(ch) for ch in f"{self.id}:{self.hand_no}:{self.stage}:{len(self.action_log)}:{player.id}:{player.bet}:{self.current_bet}:{self.pot}")
        strength = round(self._bot_strength(player), 3)
        pressure = round(max(0, self.current_bet - player.bet) / max(1, player.chips + player.bet), 3)
        raw_roll = Random(seed).random()
        roll = round(raw_roll + strength * 0.35 - pressure * 0.45, 3)
        return {"strength": strength, "pressure": pressure, "roll": roll, "seed": seed}

    @staticmethod
    def _hand_tier(rank: int) -> str:
        if rank >= 7:
            return "monster"
        if rank >= 5:
            return "strong"
        if rank >= 2:
            return "solid"
        return "weak"

    def _remember_action(self, player: Player, action: str, paid: int = 0, raise_by: int = 0) -> None:
        speech = action.upper() + (f" {raise_by}" if action in {"bet", "raise"} else "")
        self.last_action = {
            "player_id": player.id,
            "player_name": player.name,
            "action": action,
            "speech": speech,
            "paid": paid,
            "raise_by": raise_by,
            "street_bet": player.bet,
            "current_bet": self.current_bet,
            "pot": self.pot,
        }

    def _log(self, text: str) -> None:
        self.message = text
        self.action_log.append(text)
        self.action_log = self.action_log[-20:]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "dealer": self.dealer,
            "stage": self.stage,
            "deck": [str(c) for c in self.deck],
            "board": [str(c) for c in self.board],
            "pot": self.pot,
            "current_bet": self.current_bet,
            "current_player": self.current_player,
            "current_player_id": self.players[self.current_player].id if self.players else None,
            "hand_no": self.hand_no,
            "winner_ids": self.winner_ids,
            "message": self.message,
            "action_log": self.action_log,
            "last_action": self.last_action,
            
            "user_raise_count": self.user_raise_count,
            "user_call_count": self.user_call_count,
            "user_fold_count": self.user_fold_count,
            
            # [추가] 실력 제어 상태 직렬화 주입
            "user_total_hands": self.user_total_hands,
            "user_win_count": self.user_win_count,
            
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "chips": p.chips,
                    "is_human": p.is_human,
                    "hand": [str(c) for c in p.hand],
                    "bet": p.bet,
                    "folded": p.folded,
                    "all_in": p.all_in,
                    "acted": p.acted,
                }
                for p in self.players
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Table":
        table = cls(
            id=data["id"],
            small_blind=data.get("small_blind", 10),
            big_blind=data.get("big_blind", 20),
            dealer=data.get("dealer", 0),
            stage=data.get("stage", "waiting"),
            deck=cards_from_text(data.get("deck", [])),
            board=cards_from_text(data.get("board", [])),
            pot=data.get("pot", 0),
            current_bet=data.get("current_bet", 0),
            current_player=data.get("current_player", 0),
            hand_no=data.get("hand_no", 0),
            winner_ids=data.get("winner_ids", []),
            message=data.get("message", ""),
            action_log=data.get("action_log", []),
            last_action=data.get("last_action", {}),
            
            user_raise_count=data.get("user_raise_count", 0),
            user_call_count=data.get("user_call_count", 0),
            user_fold_count=data.get("user_fold_count", 0),
            
            # [추가] 리로드 시 바인딩 복구
            user_total_hands=data.get("user_total_hands", 0),
            user_win_count=data.get("user_win_count", 0),
        )
        table.players = [
            Player(
                id=p["id"],
                name=p["name"],
                chips=p.get("chips", 1000),
                is_human=p.get("is_human", False),
                hand=cards_from_text(p.get("hand", [])),
                bet=p.get("bet", 0),
                folded=p.get("folded", False),
                all_in=p.get("all_in", False),
                acted=p.get("acted", False),
            )
            for p in data.get("players", [])
        ]
        return table