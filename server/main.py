from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List
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
connected_clients: List[WebSocket] = []


@app.get("/")
async def root():
    return {"message": "Server running"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Accept handshake from client
    await websocket.accept()
    print("Client connected")

    # Get client_address
    client_address = str(websocket.client.host) + ":" + str(websocket.client.port)

    # Add client to connected_clients
    connected_clients.append(websocket)

    try:
        # While connection is open, listen for messages
        while True:
            message = await websocket.receive_text()
            print(f"Received from client: {message}")

            # Broadcast message to connected_clients
            for client in connected_clients:
                await client.send_text(f"{client_address}: {message}")
    except WebSocketDisconnect:
        # On disconnect, remove client from connected_clients
        connected_clients.remove(websocket)
        print("Client disconnected")


# Runs FastAPI server via Uvicorn from command line
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
