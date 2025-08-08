from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from logging import error
from nanoid import generate
from pydantic import BaseModel
from typing import Any, Dict, List
import json
import random
import uvicorn

# Create FastAPI app
app = FastAPI()

# Add CORS middleware to FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


MAX_PLAYERS = 4

# fmt: off
DECK = [
    "2H", "3H", "4H", "5H", "6H", "7H", "8H", "9H", "10H", "JH", "QH", "KH", "AH", # Hearts
    "2D", "3D", "4D", "5D", "6D", "7D", "8D", "9D", "10D", "JD", "QD", "KD", "AD", # Diamonds
    "2C", "3C", "4C", "5C", "6C", "7C", "8C", "9C", "10C", "JC", "QC", "KC", "AC", # Clubs
    "2S", "3S", "4S", "5S", "6S", "7S", "8S", "9S", "10S", "JS", "QS", "KS", "AS", # Spades
]
# fmt: on

# Initiate game state
game_state: Dict[str, Any] = {
    "deck": DECK.copy(),
    "discard_pile": [],
    "round": 0,
    "status": "waiting",  # waiting, playing, finished
    "turn": 0,
}

# Initiate players
players: Dict[str, Player] = {}

# Initiate session ID to WebSocket map
session_to_socket: Dict[str, WebSocket] = {}


def shuffle_deck():
    random.shuffle(game_state["deck"])


def deal_cards():
    deck = game_state["deck"]
    hand_size = 3

    for player in players.values():
        player.hand = deck[:hand_size]
        deck[:] = deck[hand_size:]


def play_card(session_id: str, card: str):
    player = players.get(session_id)

    if player and card in player.hand:
        player.hand.remove(card)
        game_state["discard_pile"].append(card)


async def broadcast(payload: Dict[str, Any]):
    for socket in session_to_socket.values():
        try:
            await socket.send_json(payload)
        except Exception:
            error(f"Error broadcasting to {socket.client.host}:{socket.client.port}")


def generate_session_id() -> str:
    return generate(alphabet="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", size=4)


def add_player(session_id: str):
    players[session_id] = Player(
        name=f"Player {session_id}",
        session_id=session_id,
    )


def connect_player(session_id: str, websocket: WebSocket):
    session_to_socket[session_id] = websocket


def disconnect_player(session_id: str):
    del session_to_socket[session_id]


def get_players() -> Dict[str, Player]:
    return {player.session_id: player.to_dict() for player in players.values()}


@app.get("/")
async def root():
    return {"message": "Server running"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Accept handshake from client
    await websocket.accept()

    # Get session ID from query params
    session_id = websocket.query_params.get("session_id")

    # If no or invalid session ID
    if not session_id or session_id not in players:
        # Generate new session ID
        session_id = generate_session_id()

        # If space for new player, add player
        if len(players) < MAX_PLAYERS:
            add_player(session_id)

            # Broadcast new player
            await broadcast(
                {
                    "players": get_players(),
                }
            )

        # Else, close WebSocket connection
        else:
            # TODO: Message client that game is full
            await websocket.close()
            return

    # Map session ID to WebSocket
    connect_player(session_id, websocket)

    # Send game state to client
    await websocket.send_json(
        {
            "game_state": game_state,
            "players": get_players(),
            "session_id": session_id,
        }
    )

    try:
        # While connection is open, listen for messages from client
        while True:
            message = await websocket.receive_text()
            action = json.loads(message).get("action")

            if action == "start_game":
                game_state["status"] = "playing"

                shuffle_deck()
                deal_cards()

            elif action == "play_card":
                card = json.loads(message).get("card")

                play_card(session_id, card)

            elif action == "next_round":
                game_state["round"] += 1

            await broadcast(
                {
                    "game_state": game_state,
                    "players": get_players(),
                }
            )

    # Handle disconnect
    except WebSocketDisconnect:
        if session_id in session_to_socket:
            disconnect_player(session_id)


# Runs FastAPI server via Uvicorn from command line
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
