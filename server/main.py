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


class GamePhase(Enum):
    WAITING = auto()
    PLAYING = auto()


class Trick(BaseModel):
    cards: List[str] = []
    leading_suit: str = ""
    winning_card: str = ""
    winning_player: str = ""


def give_trick_to_player(trick: Trick, session_id: str):
    player = players.get(session_id)

    if player:
        player.tricks.append(trick)


class PlayerType(Enum):
    BOT = auto()
    HUMAN = auto()


class GameState(BaseModel):
    current_trick: Trick = Trick()
    deck: List[str] = []
    discard_pile: List[str] = []
    game_phase: GamePhase = GamePhase.WAITING
    round: int
    turn_index: int = 0
    turn_order: List[str] = []
    turn_player: str = ""
    turn_start_index: int = 0

    def advance_turn(self):
        self.turn_index += 1

        if self.turn_index >= len(self.turn_order):
            self.turn_index = 0

        if self.turn_index == self.turn_start_index:
            self.advance_trick()

        self.turn_player = self.get_turn_player()

        if is_player_bot(self.turn_player):
            asyncio.create_task(schedule_bot_move(self.turn_player))

    def advance_trick(self):
        self.current_trick.cards = self.discard_pile
        give_trick_to_player(self.current_trick, self.current_trick.winning_player)

        self.turn_index = self.turn_order.index(self.current_trick.winning_player)
        self.turn_start_index = self.turn_index

        self.discard_pile = []
        self.current_trick = Trick()

    def get_turn_player(self) -> str:
        if self.turn_order:
            return self.turn_order[self.turn_index]
        else:
            return ""

    def is_card_winning(self, card: str) -> bool:
        if not self.current_trick.winning_card:
            return True

        card_suit = parse_card(card)[1]

        if card_suit != self.current_trick.leading_suit:
            return False

        winning_card_rank = parse_card(self.current_trick.winning_card)[0]
        card_rank = parse_card(card)[0]

        return card_rank > winning_card_rank

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_trick": self.current_trick.model_dump(),
            "deck": self.deck,
            "discard_pile": self.discard_pile,
            "game_phase": self.game_phase.name,
            "round": self.round,
            "turn_index": self.turn_index,
            "turn_order": self.turn_order,
            "turn_player": self.turn_player,
        }


class Player(BaseModel):
    hand: List[str] = []
    name: str
    session_id: str
    tricks: List[Trick] = []
    type: PlayerType

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hand": self.hand,
            "name": self.name,
            "session_id": self.session_id,
            "tricks": [trick.model_dump() for trick in self.tricks],
            "type": self.type.name,
        }


MAX_PLAYERS = 2

DECK = [
    # fmt: off
    "2H", "3H", "4H", "5H", "6H", "7H", "8H", "9H", "10H", "JH", "QH", "KH", "AH",
    "2D", "3D", "4D", "5D", "6D", "7D", "8D", "9D", "10D", "JD", "QD", "KD", "AD",
    "2C", "3C", "4C", "5C", "6C", "7C", "8C", "9C", "10C", "JC", "QC", "KC", "AC",
    "2S", "3S", "4S", "5S", "6S", "7S", "8S", "9S", "10S", "JS", "QS", "KS", "AS",
    # fmt: on
]

game_state = GameState(
    current_trick=Trick(),
    deck=DECK.copy(),
    discard_pile=[],
    game_phase=GamePhase.WAITING,
    round=0,
    turn_index=0,
    turn_order=[],
    turn_player="",
)

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
                start_game()

            elif action == "play_card":
                await play_card(session_id, card)

            await broadcast(
                {
                    "game_state": game_state.to_dict(),
                    "players": get_players(),
                }
            )
    except WebSocketDisconnect:
        if session_id in session_to_socket:
            disconnect_player(session_id)


def add_player(session_id: str):
    players[session_id] = Player(
        name=f"Player {session_id}",
        session_id=session_id,
        type=PlayerType.HUMAN,
    )


async def broadcast(payload: Dict[str, Any]):
    for socket in session_to_socket.values():
        try:
            await socket.send_json(payload)
        except Exception:
            error(f"Error broadcasting to {socket.client.host}:{socket.client.port}")


def connect_player(session_id: str, websocket: WebSocket):
    session_to_socket[session_id] = websocket


def deal_cards():
    deck = game_state.deck
    hand_size = 13

    for player in players.values():
        player.hand = deck[:hand_size]
        deck[:] = deck[hand_size:]


def disconnect_player(session_id: str):
    del session_to_socket[session_id]


def draw_deck(session_id: str, card: str):
    player = players.get(session_id)
    deck = game_state.deck

    if player and card in deck:
        deck.remove(card)
        player.hand.append(card)


def draw_discard(session_id: str, card: str):
    player = players.get(session_id)
    discard_pile = game_state.discard_pile

    if player and card in discard_pile:
        discard_pile.remove(card)
        player.hand.append(card)


def generate_session_id() -> str:
    return generate(alphabet="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", size=4)


def get_players() -> Dict[str, Player]:
    return {player.session_id: player.to_dict() for player in players.values()}


def move_card_left(session_id: str, card: str):
    player = players.get(session_id)

    if player and card in player.hand:
        current_index = player.hand.index(card)
        new_index = current_index - 1

        if current_index > 0:
            player.hand.pop(current_index)
            player.hand.insert(new_index, card)


def move_card_right(session_id: str, card: str):
    player = players.get(session_id)

    if player and card in player.hand:
        current_index = player.hand.index(card)
        new_index = current_index + 1

        if current_index < len(player.hand) - 1:
            player.hand.pop(current_index)
            player.hand.insert(new_index, card)


def has_suit_in_hand(suit: str, hand: List[str]) -> bool:
    return any(parse_card(card)[1] == suit for card in hand)


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

    if len(game_state.discard_pile) == 1:
        game_state.current_trick.leading_suit = card[-1]
        game_state.current_trick.winning_card = card
        game_state.current_trick.winning_player = session_id
    elif game_state.is_card_winning(card):
        game_state.current_trick.winning_card = card
        game_state.current_trick.winning_player = session_id

    await broadcast(
        {
            "game_state": game_state.to_dict(),
            "players": get_players(),
        }
    )

    await asyncio.sleep(1)
    game_state.advance_turn()

    await broadcast(
        {
            "game_state": game_state.to_dict(),
            "players": get_players(),
        }
    )


def set_turn_order():
    for session_id in players:
        game_state.turn_order.append(session_id)


def shuffle_deck():
    random.shuffle(game_state.deck)


def start_game():
    if len(players) < 4:
        while len(players) < 4:
            add_bot()

    game_state.game_phase = GamePhase.PLAYING
    set_turn_order()
    game_state.turn_player = game_state.get_turn_player()
    shuffle_deck()
    deal_cards()


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


async def schedule_bot_move(session_id: str):
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

    await asyncio.sleep(1)
    await simulate_message(session_id, card_to_play)


async def simulate_message(session_id: str, card: str):
    await play_card(session_id, card)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
