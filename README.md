# 🚛 dumptrick

## Background

My family plays a [Hearts](<https://www.wikipedia.org/wiki/hearts_(card_game)>) variant we call Dump Truck. This project is a web-based implementation for us to play remotely ☺️

## How to play

### How to win

The lowest total score after round 5 wins.

### Game sequence

- At the start of each round, the deck is shuffled and dealt to all players.
- Each round consists of **tricks**:

  1. The starting player plays the first card.
  2. If possible, the other players must follow suit. Otherwise, they may play any card.
  3. The player with the highest card of the lead suit wins the trick.
  4. The winner of the trick leads the next trick.

- A round ends when all cards are played. The starting player rotates each round.

### Scoring

- After each trick, points are assigned based on the cards in the trick.
- Each round adds new penalties. By round 5, all apply:

  - **Round 1**: +1 for every card
  - **Round 2**: +10 for every heart
  - **Round 3**: +25 for every queen
  - **Round 4**: +50 for the king of spades
  - **Round 5**: +100 for the last trick

### Details

- **Players**: 4
- **Deck**: Standard 52 cards (no jokers)

## Quick start

### Prerequisites

- `git`
- `npm`
- `python3`

### Clone this repo

```shell
git clone https://github.com/jjoak3/dumptrick.git
cd dumptrick
```

### Set up and start the server

1. At the root, create and activate the virtual environment:

```shell
python3 -m venv .venv
source .venv/bin/activate
```

2. Install the requirements:

```shell
pip install requirements.txt
```

3. In the `server` directory, start the server:

```shell
cd server
python3 main.py
```

### Set up and run the client

1. In the `client` directory, install the dependencies:

```shell
cd client
npm install
```

2. Create a `.env` file in the `client` directory with the server host URL:

```shell
echo "VITE_SERVER_HOST=localhost:8000" > .env
```

3. Start the client development environment:

```shell
npm run dev
```

4. Visit the localhost URL shown in the terminal (e.g. `http://localhost:5173`)

## Overview

### Technologies

- **Client**: `vite`
- **Server**: `fastapi`, `uvicorn`

### Project structure

#### `server/`

- `main.py`
  - Initiates the FastAPI app, WebSocket server, and `GameEngine` service.
- `models.py`
  - Defines game classes like `GameState` and `Player`.
  - `Player` stores a player‘s data including the WebSocket object for managing their connection.
- `services.py`
  - Provides services that manipulate the game’s objects. For example, `GameEngine` which handles the game flow (e.g. bot/player actions, turn sequence, etc.) and orchestrates the `GameState` and `Player` objects accordingly.
- `constants.py`, `enums.py`
  - Defines constants used across the app.
- `helpers.py`
  - Contains generic functions like `parse_card` which accepts a string as input (e.g. `”KS”`) and outputs the rank and suit as a tuple (e.g. `(13, “S”)`).

#### `client/`

- `src/App.tsx`
  - Connects to the WebSocket server and renders the game UI. Ideally, all logic (including calculations) are handled server-side, and the client simply renders the state it receives from the server.
  - This script also stores a user’s `player_id` in their client’s localstorage when it connects to the server to persist their session.
- `src/App.css`
  - Contains all styles for the game UI.

## Someday (Lord knows when)

- [ ] Database (i.e. `redis`)
- [ ] Rooms
- [x] Server-side error and event logs
