from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import uvicorn

from enums import GamePhase
from helpers import generate_player_id
from services import GameEngine


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


game_engine = GameEngine()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    player_id = websocket.query_params.get("player_id")
    if game_engine.players.is_new_player(player_id):
        if game_engine.players.is_full():
            await websocket.close()
            return

        player_id = generate_player_id()
        game_engine.players.add_player(player_id)

    player = game_engine.players[player_id]
    player.set_websocket(websocket)

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

            if action == "update_name":
                player.update_name(data.get("name"))

            elif action == "start_game":
                game_engine.start_game()

            elif action == "play_card":
                await game_engine.play_card(player, data.get("card"))
                await game_engine.players.broadcast(
                    {
                        "game_state": game_engine.game_state.to_dict(),
                        "players": game_engine.players.to_dict(),
                    }
                )
                await asyncio.sleep(0.5)
                game_engine.advance_turn()
                await handle_bot_turns()

            elif action == "end_game":
                game_engine.reset()

            await game_engine.players.broadcast(
                {
                    "game_state": game_engine.game_state.to_dict(),
                    "players": game_engine.players.to_dict(),
                }
            )
    except WebSocketDisconnect:
        player.clear_websocket()

        if game_engine.game_state.game_phase == GamePhase.NOT_STARTED:
            del game_engine.players[player_id]

        await game_engine.players.broadcast({"players": game_engine.players.to_dict()})


async def handle_bot_turns():
    while game_engine.game_state.game_phase == GamePhase.IN_PROGRESS:
        next_player = game_engine.players.get(game_engine.game_state.current_player_id)
        if not next_player:
            break
        if not next_player.is_bot():
            break

        card = game_engine.bot_strategy.choose_card(
            next_player,
            game_engine.game_state.current_trick,
        )

        await game_engine.play_card(next_player, card)
        await game_engine.players.broadcast(
            {
                "game_state": game_engine.game_state.to_dict(),
                "players": game_engine.players.to_dict(),
            }
        )
        await asyncio.sleep(0.5)
        game_engine.advance_turn()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
