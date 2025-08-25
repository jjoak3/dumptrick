from enum import auto, Enum
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from logging import error
from nanoid import generate
from pydantic import BaseModel
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


class GamePhase(Enum):
    NOT_STARTED = auto()
    STARTED = auto()
    GAME_OVER = auto()


class PlayerType(Enum):
    BOT = auto()
    HUMAN = auto()


class Trick(BaseModel):
    cards: List[str] = []
    is_last_trick: bool = False
    leading_suit: str = ""
    winner: str = ""
    winning_card: str = ""

    def is_winning_card(self, card: str) -> bool:
        if not self.winning_card:
            return True

        card_suit = parse_card(card)[1]

        if card_suit != self.leading_suit:
            return False

        winning_card_rank = parse_card(self.winning_card)[0]
        card_rank = parse_card(card)[0]

        return card_rank > winning_card_rank

    def update_trick(self, card: str, session_id: str):
        if not self.leading_suit:
            self.leading_suit = card[-1]

        if self.is_winning_card(card):
            self.winning_card = card
            self.winner = session_id


class Player(BaseModel):
    hand: List[str] = []
    is_winner: bool = False
    name: str
    scores: List[int] = []
    session_id: str
    total_score: int = 0
    tricks: List[Trick] = []
    type: PlayerType

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hand": self.hand,
            "name": self.name,
            "is_winner": self.is_winner,
            "scores": self.scores,
            "session_id": self.session_id,
            "total_score": self.total_score,
            "tricks": [trick.model_dump() for trick in self.tricks],
            "type": self.type.name,
        }


class GameState(BaseModel):
    current_trick: Trick = Trick()
    deck: List[str] = DECK.copy()
    discard_pile: List[str] = []
    game_phase: GamePhase = GamePhase.NOT_STARTED
    round: int = 0
    round_start_index: int = 0
    turn_order: List[str] = []
    turn_order_index: int = 0
    turn_player: str = ""
    trick_start_index: int = 0

    def start_game(self):
        if len(players) < 4:
            while len(players) < 4:
                add_bot()

        self.game_phase = GamePhase.STARTED

        self.set_turn_order()
        self.set_turn_player()

        self.shuffle_deck()
        self.deal_cards()

    def end_game(self):
        self.game_phase = GamePhase.GAME_OVER
        get_winners()

    def restart_game(self):
        self.game_phase = GamePhase.STARTED

        self.round = 0
        self.round_start_index = 0

        self.trick_start_index = 0

        self.turn_order_index = 0
        self.set_turn_player()

        self.current_trick = Trick()
        self.discard_pile.clear()

        self.deck = DECK.copy()
        self.shuffle_deck()
        self.deal_cards()

        clear_player_scores()

    def advance_turn(self):
        self.turn_order_index = self.increment_index(self.turn_order_index)
        self.set_turn_player()

        if self.is_trick_over():
            self.advance_trick()

        if self.is_round_over():
            self.advance_round()

        if is_player_bot(self.turn_player):
            asyncio.create_task(schedule_bot_turn(self.turn_player))

    def advance_trick(self):
        self.current_trick.cards = self.discard_pile.copy()
        self.discard_pile.clear()

        if self.is_round_over():
            self.current_trick.is_last_trick = True

        award_trick_to_player(self.current_trick, self.current_trick.winner)

        self.turn_order_index = self.turn_order.index(self.current_trick.winner)
        self.trick_start_index = self.turn_order_index
        self.set_turn_player()

        self.current_trick = Trick()

    def advance_round(self):
        self.round += 1
        calculate_scores()

        if self.round >= 6:
            return self.end_game()

        self.round_start_index = self.increment_index(self.round_start_index)

        self.turn_order_index = self.round_start_index
        self.trick_start_index = self.turn_order_index
        self.set_turn_player()

        self.deck = DECK.copy()
        self.shuffle_deck()
        self.deal_cards()

        clear_player_tricks()

    def deal_cards(self):
        hand_size = 13

        for player in players.values():
            player.hand = self.deck[:hand_size]
            self.deck[:] = self.deck[hand_size:]

            player.hand.sort(key=get_card_sort_key)

    def increment_index(self, index: int) -> int:
        return (index + 1) % len(self.turn_order)

    def is_round_over(self) -> bool:
        for player in players.values():
            if player.hand:
                return False

        return True

    def is_trick_over(self) -> bool:
        return self.turn_order_index == self.trick_start_index

    def set_turn_order(self):
        self.turn_order = [player.session_id for player in players.values()]

    def set_turn_player(self):
        self.turn_player = self.turn_order[self.turn_order_index]

    def shuffle_deck(self):
        random.shuffle(self.deck)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "discard_pile": self.discard_pile,
            "game_phase": self.game_phase.name,
            "turn_player": self.turn_player,
        }


game_state = GameState()
players: Dict[str, Player] = {}
session_to_socket: Dict[str, WebSocket] = {}


@app.get("/")
async def root():
    return {"message": "Server running"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    session_id = websocket.query_params.get("session_id")
    if not session_id or session_id not in players:
        session_id = generate_session_id()

        if len(players) < MAX_PLAYERS:
            add_player(session_id)
            await broadcast({"players": get_players()})
        else:
            await websocket.close()
            return

    connect_player(session_id, websocket)

    await websocket.send_json(
        {
            "game_state": game_state.to_dict(),
            "players": get_players(),
            "session_id": session_id,
        }
    )

    try:
        while True:
            message = await websocket.receive_text()
            action = json.loads(message).get("action")
            card = json.loads(message).get("card")

            if action == "start_game":
                game_state.start_game()

            elif action == "play_card":
                await play_card(session_id, card)

            elif action == "restart_game":
                game_state.restart_game()

            await broadcast(
                {
                    "game_state": game_state.to_dict(),
                    "players": get_players(),
                }
            )
    except WebSocketDisconnect:
        if session_id in session_to_socket:
            disconnect_player(session_id)


"""Helpers"""


def get_card_sort_key(card: str) -> tuple[int, int]:
    rank, suit = parse_card(card)
    return (SUIT_ORDER.index(suit), rank)


def has_suit_in_hand(suit: str, hand: List[str]) -> bool:
    return any(parse_card(card)[1] == suit for card in hand)


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


"""WebSockets"""


async def broadcast(payload: Dict[str, Any]):
    for socket in session_to_socket.values():
        try:
            await socket.send_json(payload)
        except Exception:
            error(f"Error broadcasting to {socket.client.host}:{socket.client.port}")


def connect_player(session_id: str, websocket: WebSocket):
    session_to_socket[session_id] = websocket


def disconnect_player(session_id: str):
    del session_to_socket[session_id]


def generate_session_id() -> str:
    return generate(alphabet="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", size=4)


"""Players"""


def add_player(session_id: str):
    players[session_id] = Player(
        name=f"Player {session_id}",
        session_id=session_id,
        type=PlayerType.HUMAN,
    )


def award_trick_to_player(trick: Trick, session_id: str):
    player = players.get(session_id)

    if player:
        player.tricks.append(trick)


def clear_player_scores():
    for player in players.values():
        player.scores.clear()


def clear_player_tricks():
    for player in players.values():
        player.tricks.clear()


def get_players() -> Dict[str, Player]:
    return {player.session_id: player.to_dict() for player in players.values()}


"""Bots"""


def add_bot():
    session_id = generate_session_id()

    players[session_id] = Player(
        name=f"Bot {session_id}",
        session_id=session_id,
        type=PlayerType.BOT,
    )


def is_player_bot(session_id: str) -> bool:
    player = players.get(session_id)

    if player and player.type == PlayerType.BOT:
        return True

    return False


async def schedule_bot_turn(session_id: str):
    player = players.get(session_id)
    if not player:
        return

    leading_suit = game_state.current_trick.leading_suit

    matching_cards = []
    for card in player.hand:
        if parse_card(card)[1] == leading_suit:
            matching_cards.append(card)

    if matching_cards:
        card_to_play = min(matching_cards, key=parse_card)
    else:
        card_to_play = max(player.hand, key=parse_card)

    await asyncio.sleep(0.25)
    await simulate_message(session_id, card_to_play)


async def simulate_message(session_id: str, card: str):
    await play_card(session_id, card)


"""Game state"""


async def play_card(session_id: str, card: str):
    player = players.get(session_id)

    if not player and card not in player.hand:
        return

    suit = parse_card(card)[1]
    leading_suit = game_state.current_trick.leading_suit

    if (
        leading_suit
        and has_suit_in_hand(leading_suit, player.hand)
        and suit != leading_suit
    ):
        return

    # TODO: Add turn_phase enum to handle the end of a turn rather than resetting turn_player
    game_state.turn_player = ""
    player.hand.remove(card)
    game_state.discard_pile.append(card)

    game_state.current_trick.update_trick(card, session_id)

    await broadcast(
        {
            "game_state": game_state.to_dict(),
            "players": get_players(),
        }
    )

    await asyncio.sleep(0.25)
    game_state.advance_turn()

    await broadcast(
        {
            "game_state": game_state.to_dict(),
            "players": get_players(),
        }
    )


"""Scoring"""


def calculate_scores():
    current_round = game_state.round

    for player in players.values():
        score = 0

        if current_round == 1:
            score += get_trick_count_penalty(player.tricks)
        elif current_round == 2:
            score += get_hearts_penalty(player.tricks)
        elif current_round == 3:
            score += get_queens_penalty(player.tricks)
        elif current_round == 4:
            score += get_ks_penalty(player.tricks)
        elif current_round == 5:
            score += get_last_trick_penalty(player.tricks)
        elif current_round == 6:
            score += get_trick_count_penalty(player.tricks)
            score += get_hearts_penalty(player.tricks)
            score += get_queens_penalty(player.tricks)
            score += get_ks_penalty(player.tricks)
            score += get_last_trick_penalty(player.tricks)

        player.scores.append(score)


def get_trick_count_penalty(tricks: List[Trick]) -> int:
    return len(tricks)


def get_hearts_penalty(tricks: List[Trick]) -> int:
    penalty = 0

    for trick in tricks:
        for card in trick.cards:
            if parse_card(card)[1] == "H":
                penalty += 10

    return penalty


def get_queens_penalty(tricks: List[Trick]) -> int:
    penalty = 0

    for trick in tricks:
        for card in trick.cards:
            if card in ["QC", "QD", "QH", "QS"]:
                penalty += 25

    return penalty


def get_ks_penalty(tricks: List[Trick]) -> int:
    penalty = 0

    for trick in tricks:
        if "KS" in trick.cards:
            penalty += 50

    return penalty


def get_last_trick_penalty(tricks: List[Trick]) -> int:
    penalty = 0

    for trick in tricks:
        if trick.is_last_trick:
            penalty += 100

    return penalty


def get_winners():
    total_scores = []

    for player in players.values():
        total_scores.append((player.session_id, sum(player.scores)))

    lowest_score = min([score for _, score in total_scores])

    for session_id, score in total_scores:
        if score == lowest_score:
            players[session_id].is_winner = True


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
