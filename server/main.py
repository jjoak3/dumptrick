from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from logging import error
from nanoid import generate
from pydantic import BaseModel
from typing import Any, Dict, List
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


class GameState(BaseModel):
    deck: List[str] = []
    discard_pile: List[str] = []
    round: int
    status: str
    turn: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deck": self.deck,
            "discard_pile": self.discard_pile,
            "round": self.round,
            "status": self.status,
            "turn": self.turn,
        }


class Player(BaseModel):
    hand: List[str] = []
    name: str
    session_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hand": self.hand,
            "name": self.name,
            "session_id": self.session_id,
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

game_state: GameState = {
    "deck": DECK.copy(),
    "discard_pile": [],
    "round": 0,
    "status": "waiting",
    "turn": 0,
}

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
            "game_state": game_state,
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

            elif action == "draw_deck":
                draw_deck(session_id, card)

            elif action == "draw_discard":
                draw_discard(session_id, card)

            elif action == "move_card_left":
                move_card_left(session_id, card)

            elif action == "move_card_right":
                move_card_right(session_id, card)

            elif action == "play_card":
                play_card(session_id, card)

            await broadcast(
                {
                    "game_state": game_state,
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
    deck = game_state["deck"]
    hand_size = 13

    for player in players.values():
        player.hand = deck[:hand_size]
        deck[:] = deck[hand_size:]


def disconnect_player(session_id: str):
    del session_to_socket[session_id]


def draw_deck(session_id: str, card: str):
    player = players.get(session_id)
    deck = game_state["deck"]

    if player and card in deck:
        deck.remove(card)
        player.hand.append(card)


def draw_discard(session_id: str, card: str):
    player = players.get(session_id)
    discard_pile = game_state["discard_pile"]

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


def play_card(session_id: str, card: str):
    player = players.get(session_id)

    if player and card in player.hand:
        player.hand.remove(card)
        game_state["discard_pile"].append(card)


def shuffle_deck():
    random.shuffle(game_state["deck"])


def start_game():
    game_state["status"] = "playing"
    shuffle_deck()
    deal_cards()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
