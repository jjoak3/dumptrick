from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from logging import error
from typing import Any, Dict, List
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

# Initiate list of connected WebSocket clients
connected_sockets: List[WebSocket] = []


# Broadcasts provided payload to connected_sockets
async def broadcast(payload: Dict[str, Any]):
    for socket in connected_sockets:
        try:
            await socket.send_json(payload)
        except Exception:
            error(f"Error broadcasting to {socket.client.host}:{socket.client.port}")


# Returns list of client addresses
def get_client_addresses() -> List[str]:
    return [
        f"{socket.client.host}:{socket.client.port}" for socket in connected_sockets
    ]


@app.get("/")
async def root():
    return {"message": "Server running"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Accept handshake from client
    await websocket.accept()

    # Get client_address
    client_address = str(websocket.client.host) + ":" + str(websocket.client.port)

    # Add client to connected_sockets
    connected_sockets.append(websocket)

    # Send client_address to client
    await websocket.send_json({"client_address": client_address})

    # Broadcast connect message
    await broadcast(
        {
            "client_addresses": get_client_addresses(),
            "message": f"{client_address} connected",
        }
    )

    try:
        # While connection is open, listen for messages from client
        while True:
            message = await websocket.receive_text()

            # Broadcast message from client
            await broadcast(
                {
                    "message": message,
                }
            )
    except WebSocketDisconnect:
        # On disconnect, remove client from connected_sockets
        connected_sockets.remove(websocket)

        # Broadcast disconnect message
        await broadcast(
            {
                "client_addresses": get_client_addresses(),
                "message": f"{client_address} disconnected",
            }
        )


# Runs FastAPI server via Uvicorn from command line
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
