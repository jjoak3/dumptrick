from datetime import datetime
from fastapi import WebSocket
from typing import Any, Dict, List

from constants import GAME_EXPIRATION_SECONDS, MAX_PLAYERS
from enums import GamePhase, PlayerType, TurnPhase
from helpers import generate_player_id, is_higher_rank, parse_card


class GameState:
    def __init__(self):
        self.current_round: int = 0
        self.current_trick: Trick = Trick()
        self.created_at: datetime = datetime.now()
        self.discard_pile: List[str] = []
        self.game_phase: GamePhase = GamePhase.NOT_STARTED
        self.round_start_index: int = 0
        self.turn_order: List[str] = []
        self.current_turn_index: int = 0
        self.turn_phase: TurnPhase = TurnPhase.NOT_STARTED
        self.trick_start_index: int = 0

    @property
    def current_player_id(self) -> str:
        if not self.turn_order:
            return ""
        return self.turn_order[self.current_turn_index]

    def is_expired(self) -> bool:
        if self.game_phase == GamePhase.NOT_STARTED:
            return False

        elapsed_time = datetime.now() - self.created_at
        return elapsed_time.total_seconds() > GAME_EXPIRATION_SECONDS

    def reset(self):
        self.__init__()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_player_id": self.current_player_id,
            "current_round": self.current_round,
            "current_trick": self.current_trick.to_dict(),
            "discard_pile": self.discard_pile,
            "game_phase": self.game_phase.name,
            "turn_phase": self.turn_phase.name,
        }


class Player:
    def __init__(
        self,
        name: str,
        player_id: str,
        type: PlayerType,
    ):
        self.hand: List[str] = []
        self.is_winner: bool = False
        self.name: str = name
        self.player_id: str = player_id
        self.scores: List[int] = []
        self.tricks: List[Trick] = []
        self.type: PlayerType = type
        self.websocket: WebSocket = None

    def set_websocket(self, websocket: WebSocket):
        self.websocket = websocket

    def clear_websocket(self):
        self.websocket = None

    async def send(self, payload: Dict[str, Any]):
        if not self.websocket:
            return

        try:
            await self.websocket.send_json(payload)
        except Exception:
            self.clear_websocket()

    def is_bot(self) -> bool:
        return self.type == PlayerType.BOT

    def has_suit_in_hand(self, suit: str) -> bool:
        for card in self.hand:
            card_suit = parse_card(card)[1]
            if card_suit == suit:
                return True
        return False

    def take_trick(self, trick: "Trick"):
        self.tricks.append(trick)

    def reset(self):
        self.hand.clear()
        self.is_winner = False
        self.scores.clear()
        self.tricks.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hand": self.hand,
            "is_winner": self.is_winner,
            "name": self.name,
            "player_id": self.player_id,
            "scores": self.scores,
            "total_score": sum(self.scores),
            "tricks": [trick.to_dict() for trick in self.tricks],
        }


class Players(Dict[str, Player]):
    def __init__(self):
        super().__init__()

    def is_new_player(self, player_id: str) -> bool:
        return not player_id or player_id not in self

    def is_full(self) -> bool:
        return len(self) >= MAX_PLAYERS

    def add_player(self, player_id: str):
        self[player_id] = Player(
            name=f"Player #{player_id}",
            player_id=player_id,
            type=PlayerType.HUMAN,
        )

    def add_bots(self):
        while len(self) < MAX_PLAYERS:
            self._add_bot(generate_player_id())

    def _add_bot(self, player_id: str):
        self[player_id] = Player(
            name=f"Bot #{player_id}",
            player_id=player_id,
            type=PlayerType.BOT,
        )

    def clear_tricks(self):
        for player in self.values():
            player.tricks.clear()

    def reset(self):
        self._clear_bots()
        for player in self.values():
            player.reset()

    def _clear_bots(self):
        for bot_id in self._get_bot_ids():
            del self[bot_id]

    def _get_bot_ids(self) -> List[str]:
        bot_ids = []
        for player in self.values():
            if player.type == PlayerType.BOT:
                bot_ids.append(player.player_id)
        return bot_ids

    async def broadcast(self, payload: Dict[str, Any]):
        for player in self.values():
            await player.send(payload)

    def to_dict(self) -> Dict[str, Player]:
        return {player_id: player.to_dict() for player_id, player in self.items()}


class Trick:
    def __init__(self):
        self.cards: List[str] = []
        self.is_last_trick: bool = False
        self.leading_suit: str = ""
        self.winner_id: str = ""
        self.winning_card: str = ""

    def update(self, card: str, player_id: str):
        if not self.leading_suit:
            card_suit = card[-1]
            self.leading_suit = card_suit

        if is_higher_rank(card, self.winning_card):
            self.winning_card = card
            self.winner_id = player_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cards": self.cards,
            "leading_suit": self.leading_suit,
        }
