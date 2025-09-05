from enum import auto, Enum
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from logging import error
from nanoid import generate
from typing import Any, Dict, List
import asyncio
import json
import random
import uvicorn

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


"""Constants"""


DECK = [
    # fmt: off
    "2H", "3H", "4H", "5H", "6H", "7H", "8H", "9H", "10H", "JH", "QH", "KH", "AH",
    "2D", "3D", "4D", "5D", "6D", "7D", "8D", "9D", "10D", "JD", "QD", "KD", "AD",
    "2C", "3C", "4C", "5C", "6C", "7C", "8C", "9C", "10C", "JC", "QC", "KC", "AC",
    "2S", "3S", "4S", "5S", "6S", "7S", "8S", "9S", "10S", "JS", "QS", "KS", "AS",
    # fmt: on
]
MAX_PLAYERS = 4
SUIT_ORDER = ["D", "C", "H", "S"]


"""Helpers"""


def generate_player_id() -> str:
    return generate(alphabet="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", size=4)


def is_higher_rank(card_a: str, card_b: str) -> bool:
    if not card_a:
        return False

    if not card_b:
        return True

    card_a_rank, card_a_suit = parse_card(card_a)
    card_b_rank, card_b_suit = parse_card(card_b)

    if card_a_suit != card_b_suit:
        return False

    return card_a_rank > card_b_rank


def parse_card(card: str) -> tuple[int, str]:
    rank = card[:-1]
    suit = card[-1]

    if rank == "A":
        rank = "14"
    elif rank == "K":
        rank = "13"
    elif rank == "Q":
        rank = "12"
    elif rank == "J":
        rank = "11"

    return int(rank), suit


def rotate_index(index: int, length: int) -> int:
    return (index + 1) % length


"""Enums"""


class GamePhase(Enum):
    NOT_STARTED = auto()
    STARTED = auto()
    GAME_COMPLETE = auto()


class PlayerType(Enum):
    BOT = auto()
    HUMAN = auto()


class TurnPhase(Enum):
    NOT_STARTED = auto()
    TURN_COMPLETE = auto()


"""Services"""


class BotStrategy:
    @staticmethod
    def choose_card(player: "Player", current_trick: "Trick") -> str:
        leading_suit = current_trick.leading_suit

        matching_cards = [
            card for card in player.hand if parse_card(card)[1] == leading_suit
        ]

        if matching_cards:
            return min(matching_cards, key=parse_card)
        else:
            return max(player.hand, key=parse_card)


class DeckManager:
    def __init__(self):
        self.deck = DECK.copy()

    def shuffle(self):
        random.shuffle(self.deck)

    def deal_hands(self, num_players: int) -> List[List[str]]:
        hand_size = len(self.deck) // num_players
        hands = []

        for _ in range(num_players):
            hand = self.deck[:hand_size]
            self.deck = self.deck[hand_size:]
            hand.sort(key=self._get_card_sort_key)
            hands.append(hand)

        return hands

    def reset(self):
        self.deck = DECK.copy()

    def _get_card_sort_key(self, card: str) -> tuple[int, int]:
        rank, suit = parse_card(card)
        return (SUIT_ORDER.index(suit), rank)


class GameFlow:
    def __init__(self, game_state: "GameState", players: "Players"):
        self.game_state = game_state
        self.players = players
        self.bot_strategy = BotStrategy()
        self.deck_manager = DeckManager()

    def start_game(self):
        self.players.fill_openings_with_bots()

        self.game_state.game_phase = GamePhase.STARTED
        self._setup_new_round()

    def _setup_new_round(self):
        self.game_state.set_turn_order(self.players)

        self.deck_manager.reset()
        self.deck_manager.shuffle()
        hands = self.deck_manager.deal_hands(len(self.players))

        for i, player in enumerate(self.players.values()):
            player.hand = hands[i]

    async def play_card(self, player: "Player", card: str) -> bool:
        if not self._is_valid_play(player, card):
            return False

        player.hand.remove(card)
        self.game_state.discard_pile.append(card)
        self.game_state.current_trick.update_trick(card, player.player_id)
        self.game_state.turn_phase = TurnPhase.TURN_COMPLETE

        return True

    def _is_valid_play(self, player: "Player", card: str) -> bool:
        if card not in player.hand:
            return False

        suit = parse_card(card)[1]
        leading_suit = self.game_state.current_trick.leading_suit

        if leading_suit and player.has_suit(leading_suit) and suit != leading_suit:
            return False

        return True

    def advance_turn(self):
        self.game_state.turn_order_index = rotate_index(
            self.game_state.turn_order_index,
            len(self.game_state.turn_order),
        )
        self.game_state.turn_phase = TurnPhase.NOT_STARTED

        if self._is_trick_over():
            self._advance_trick()

        if self._is_round_over():
            self._advance_round()

    def _is_trick_over(self) -> bool:
        return self.game_state.turn_order_index == self.game_state.trick_start_index

    def _is_round_over(self) -> bool:
        for player in self.players.values():
            if player.hand:
                return False
        return True

    def _advance_trick(self):
        self.game_state.current_trick.cards = self.game_state.discard_pile.copy()
        self.game_state.discard_pile.clear()

        if self._is_round_over():
            self.game_state.current_trick.is_last_trick = True

        winner_id = self.game_state.current_trick.winner
        if not winner_id:
            return
        if winner_id not in self.players:
            return

        self.players.get(winner_id).take_trick(self.game_state.current_trick)

        self.game_state.turn_order_index = self.game_state.turn_order.index(winner_id)
        self.game_state.trick_start_index = self.game_state.turn_order_index

        self.game_state.current_trick = Trick()

    def _advance_round(self):
        self.game_state.current_round += 1
        self.players.calculate_scores(self.game_state.current_round)

        if self.game_state.current_round >= 5:
            return self._complete_game()

        self.game_state.round_start_index = rotate_index(
            self.game_state.round_start_index, len(self.game_state.turn_order)
        )
        self.game_state.turn_order_index = self.game_state.round_start_index
        self.game_state.trick_start_index = self.game_state.round_start_index

        self._setup_new_round()
        self.players.clear_tricks()

    def _complete_game(self):
        self.game_state.game_phase = GamePhase.GAME_COMPLETE
        self.players.set_winners()


class ScoreCalculator:
    @staticmethod
    def calculate_card_count_penalty(tricks: List["Trick"]) -> int:
        return sum(len(trick.cards) for trick in tricks)

    @staticmethod
    def calculate_hearts_penalty(tricks: List["Trick"]) -> int:
        penalty = 0
        for trick in tricks:
            for card in trick.cards:
                if parse_card(card)[1] == "H":
                    penalty += 10
        return penalty

    @staticmethod
    def calculate_queens_penalty(tricks: List["Trick"]) -> int:
        penalty = 0
        for trick in tricks:
            for card in trick.cards:
                if card in ["QC", "QD", "QH", "QS"]:
                    penalty += 25
        return penalty

    @staticmethod
    def calculate_ks_penalty(tricks: List["Trick"]) -> int:
        penalty = 0
        for trick in tricks:
            if "KS" in trick.cards:
                penalty += 50
        return penalty

    @staticmethod
    def calculate_last_trick_penalty(tricks: List["Trick"]) -> int:
        penalty = 0
        for trick in tricks:
            if trick.is_last_trick:
                penalty += 100
        return penalty

    @staticmethod
    def calculate_round_score(player: "Player", round_number: int) -> int:
        score = 0

        score += ScoreCalculator.calculate_card_count_penalty(player.tricks)

        if round_number >= 2:
            score += ScoreCalculator.calculate_hearts_penalty(player.tricks)
        if round_number >= 3:
            score += ScoreCalculator.calculate_queens_penalty(player.tricks)
        if round_number >= 4:
            score += ScoreCalculator.calculate_ks_penalty(player.tricks)
        if round_number >= 5:
            score += ScoreCalculator.calculate_last_trick_penalty(player.tricks)

        return score


"""Models"""


class Trick:
    def __init__(self):
        self.cards: List[str] = []
        self.is_last_trick: bool = False
        self.leading_suit: str = ""
        self.winner: str = ""
        self.winning_card: str = ""

    def update_trick(self, card: str, player_id: str):
        if not self.leading_suit:
            self.leading_suit = card[-1]

        if is_higher_rank(card, self.winning_card):
            self.winning_card = card
            self.winner = player_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cards": self.cards,
            "leading_suit": self.leading_suit,
        }


class Player:
    def __init__(
        self,
        player_id: str,
        name: str = "",
        type: PlayerType = PlayerType.HUMAN,
    ):
        self.hand: List[str] = []
        self.is_winner: bool = False
        self.name: str = name or f"Player #{player_id}"
        self.player_id: str = player_id
        self.scores: List[int] = []
        self.tricks: List[Trick] = []
        self.type: PlayerType = type or PlayerType.HUMAN
        self.websocket: WebSocket = None

    def set_websocket(self, websocket: WebSocket):
        self.websocket = websocket

    def clear_websocket(self):
        self.websocket = None

    def is_bot(self) -> bool:
        return self.type == PlayerType.BOT

    def has_suit(self, suit: str) -> bool:
        return any(parse_card(card)[1] == suit for card in self.hand)

    def take_trick(self, trick: Trick):
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
            "scores": self.scores,
            "player_id": self.player_id,
            "total_score": sum(self.scores),
            "tricks": [trick.to_dict() for trick in self.tricks],
        }


class Players(Dict[str, Player]):
    def __init__(self):
        super().__init__()
        self.score_calculator = ScoreCalculator()

    def add_player(self, player_id: str):
        self[player_id] = Player(player_id=player_id)

    def add_bot(self, player_id: str):
        self[player_id] = Player(
            name=f"Bot #{player_id}",
            player_id=player_id,
            type=PlayerType.BOT,
        )

    def fill_openings_with_bots(self):
        while len(self) < MAX_PLAYERS:
            self.add_bot(generate_player_id())

    def clear_tricks(self):
        for player in self.values():
            player.tricks.clear()

    def calculate_scores(self, current_round: int):
        for player in self.values():
            score = self.score_calculator.calculate_round_score(player, current_round)
            player.scores.append(score)

    def set_winners(self):
        total_scores = self._get_total_scores()
        if not total_scores:
            return

        lowest_score = min(total_scores.values())

        for player_id, score in total_scores.items():
            if score == lowest_score:
                self[player_id].is_winner = True

    def _get_total_scores(self) -> Dict[str, int]:
        total_scores = {}

        for player_id, player in self.items():
            total_scores[player_id] = sum(player.scores)

        return total_scores

    def reset(self):
        self._clear_bots()

        for player in self.values():
            player.reset()

    def _clear_bots(self):
        bot_ids = [
            player.player_id
            for player in self.values()
            if player.type == PlayerType.BOT
        ]
        for bot_id in bot_ids:
            del self[bot_id]

    def to_dict(self) -> Dict[str, Player]:
        return {player_id: player.to_dict() for player_id, player in self.items()}


class GameState:
    def __init__(self):
        self.current_round: int = 0
        self.current_trick: Trick = Trick()
        self.discard_pile: List[str] = []
        self.game_phase: GamePhase = GamePhase.NOT_STARTED
        self.round_start_index: int = 0
        self.turn_order: List[str] = []
        self.turn_order_index: int = 0
        self.turn_phase: TurnPhase = TurnPhase.NOT_STARTED
        self.trick_start_index: int = 0

    @property
    def current_player_id(self) -> str:
        return self.turn_order[self.turn_order_index] if self.turn_order else ""

    def set_turn_order(self, players: Players):
        self.turn_order = [player.player_id for player in players.values()]

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


"""Game controller"""


class GameController:
    def __init__(self):
        self.game_state = GameState()
        self.players = Players()
        self.game_flow = GameFlow(self.game_state, self.players)

    async def handle_action(self, action: str, player_id: str, **kwargs):
        player = self.players.get(player_id)
        if not player:
            return

        if action == "update_name":
            name = kwargs.get("name", "").strip()
            if not name:
                return

            player.name = name

        elif action == "start_game":
            if self.game_state.game_phase == GamePhase.NOT_STARTED:
                self.game_flow.start_game()

        elif action == "play_card":
            card = kwargs.get("card")
            if not card:
                return

            if self.game_state.game_phase != GamePhase.STARTED:
                return

            isValidPlay = await self.game_flow.play_card(player, card)
            if not isValidPlay:
                return

            await self._broadcast_game_state()
            self.game_flow.advance_turn()
            await self._handle_bot_turns()

        elif action == "end_game":
            self.game_state.reset()
            self.players.reset()
            self.game_flow = GameFlow(self.game_state, self.players)

    async def _handle_bot_turns(self):
        while self.game_state.game_phase == GamePhase.STARTED:
            next_player = self.players.get(self.game_state.current_player_id)
            if not next_player:
                break
            if not next_player.is_bot():
                break

            card = self.game_flow.bot_strategy.choose_card(
                next_player,
                self.game_state.current_trick,
            )
            success = await self.game_flow.play_card(next_player, card)

            if not success:
                break

            await self._broadcast_game_state()
            self.game_flow.advance_turn()

    async def _broadcast_game_state(self):
        payload = {
            "game_state": self.game_state.to_dict(),
            "players": self.players.to_dict(),
        }

        await broadcast_to_players(payload)
        await asyncio.sleep(0.5)  # Give players time to see played card

    def get_session_data(self, player_id: str) -> Dict[str, Any]:
        return {
            "game_state": self.game_state.to_dict(),
            "players": self.players.to_dict(),
            "player_id": player_id,
        }


"""Global instances"""


game_controller = GameController()


async def broadcast_to_players(payload: Dict[str, Any]):
    for player in game_controller.players.values():
        if not player.websocket:
            continue

        try:
            await player.websocket.send_json(payload)
        except Exception as e:
            player.clear_websocket()
            error(f"Error broadcasting to player {player.player_id}: {e}")


"""Endpoints"""


@app.get("/")
async def root():
    return {"message": "Server running"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    player_id = websocket.query_params.get("player_id")
    if not player_id or player_id not in game_controller.players:
        player_id = generate_player_id()

        if len(game_controller.players) >= MAX_PLAYERS:
            await websocket.close()
            return

        game_controller.players.add_player(player_id)
        await broadcast_to_players({"players": game_controller.players.to_dict()})

    game_controller.players.get(player_id).set_websocket(websocket)
    await websocket.send_json(game_controller.get_session_data(player_id))

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            action = data.get("action")
            card = data.get("card")
            name = data.get("name")

            await game_controller.handle_action(action, player_id, card=card, name=name)

            await broadcast_to_players(
                {
                    "game_state": game_controller.game_state.to_dict(),
                    "players": game_controller.players.to_dict(),
                }
            )
    except WebSocketDisconnect:
        player = game_controller.players.get(player_id)
        if not player:
            return

        player.clear_websocket()

        if game_controller.game_state.game_phase == GamePhase.NOT_STARTED:
            del game_controller.players[player_id]

        await broadcast_to_players({"players": game_controller.players.to_dict()})


"""Execution"""


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
