from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
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


@app.get("/")
async def root():
    return {"message": "Server running"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Accept handshake from client
    await websocket.accept()
    print("Client connected")
    try:
        # While connection is open, listen for messages
        while True:
            data = await websocket.receive_text()
            print(f"Received from client: {data}")

            # Echo data back to client
            await websocket.send_text(data)
    except WebSocketDisconnect:
        print("Client disconnected")


# Runs FastAPI server via Uvicorn from command line
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
