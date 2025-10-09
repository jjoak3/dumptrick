from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import logging
import os
import re
import uvicorn

from enums import GamePhase
from helpers import generate_player_id
from services import GameEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def sanitize_for_log(value: str) -> str:
    """Sanitize string values for safe logging by removing control characters."""
    if not isinstance(value, str):
        return str(value)
    # Remove control characters and newlines to prevent log injection
    return re.sub(r'[\x00-\x1F\x7F-\x9F]', '', value)


app = FastAPI()

allowed_origins = [
    "http://localhost:5173",  # Default Vite dev server port
    "http://localhost:4173",  # Default Vite preview server port
]

production_origin = os.getenv("PRODUCTION_ORIGIN")
if production_origin:
    allowed_origins.append(production_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


game_engine = GameEngine()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    if game_engine.game_state.is_expired():
        logger.info("Game state expired - resetting game")
        game_engine.reset_game()

    player_id = websocket.query_params.get("player_id")
    if game_engine.players.is_new_player(player_id):
        if game_engine.game_state.is_started():
            logger.warning(f"Connection rejected - game already in session (player_id: {player_id})")
            await websocket.close(code=1000, reason="A game is already in session.")
            return
        if game_engine.players.is_full():
            logger.warning(f"Connection rejected - lobby is full (player_id: {player_id})")
            await websocket.close(code=1000, reason="The lobby is full.")
            return

        player_id = generate_player_id()
        game_engine.players.add_player(player_id)
        logger.info(f"New player added: {player_id}")

    player = game_engine.players[player_id]
    player.set_websocket(websocket)
    logger.info(f"Player connected: {player_id}")

    await player.send(
        {
            "game_state": game_engine.game_state.to_dict(),
            "players": game_engine.players.to_dict(),
            "player_id": player_id,
        }
    )

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            action = data.get("action")
            logger.info(f"Received action '{sanitize_for_log(str(action))}' from player {player_id}")

            await game_engine.handle_action(action, data)
    except WebSocketDisconnect:
        logger.info(f"Player disconnected: {player_id}")
        player.clear_websocket()

        if game_engine.game_state.game_phase == GamePhase.NOT_STARTED:
            del game_engine.players[player_id]
            logger.info(f"Player removed from lobby: {player_id}")

        await game_engine.players.broadcast({"players": game_engine.players.to_dict()})


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
