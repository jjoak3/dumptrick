from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from logging import error
from typing import Any, Dict
import asyncio
import json
import uvicorn

from constants import MAX_PLAYERS
from enums import GamePhase
from helpers import generate_player_id
from models import GameState, Players
from services import GameFlow


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

            if self.game_state.game_phase != GamePhase.IN_PROGRESS:
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
        while self.game_state.game_phase == GamePhase.IN_PROGRESS:
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


async def broadcast_to_players(payload: Dict[str, Any]):
    for player in game_controller.players.values():
        if not player.websocket:
            continue

        try:
            await player.websocket.send_json(payload)
        except Exception as e:
            player.clear_websocket()
            error(f"Error broadcasting to player {player.player_id}: {e}")


game_controller = GameController()


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


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
