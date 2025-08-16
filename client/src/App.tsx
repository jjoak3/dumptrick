import { useState, useEffect, useRef } from 'react'

interface GameState {
  deck: string[]
  discard_pile: string[]
  round: number
  status: string
}

interface Player {
  hand: string[]
  name: string
  session_id: string
}

function App() {
  const [gameState, setGameState] = useState<GameState | undefined>(undefined)
  const [players, setPlayers] = useState<Record<string, Player>>({})
  const [sessionId, setSessionId] = useState('')
  const websocketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const storedSessionId = localStorage.getItem('session_id')
    const websocketUrl = 'ws://localhost:8000/ws' + (storedSessionId ? `?session_id=${storedSessionId}` : '')
    const websocket = new WebSocket(websocketUrl)
    websocketRef.current = websocket

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.game_state) setGameState(data.game_state)
        if (data.players) setPlayers(data.players)
        if (data.session_id) setSessionId(data.session_id)
      } catch (error) {
        console.error(error)
      }
    }

    return () => websocket.close()
  }, [])

  useEffect(() => {
    localStorage.setItem('session_id', sessionId)
  }, [sessionId])

  const handleAction = (action: string) => {
    if (websocketRef.current) {
      websocketRef.current.send(JSON.stringify({ action }))
    }
  }

  const handlePlayCard = (card: string) => {
    if (websocketRef.current) {
      websocketRef.current.send(JSON.stringify({ action: 'play_card', card: card }))
    }
  }

  const renderActionButtons = () => {
    switch (gameState?.status) {
      case 'waiting':
        return <button onClick={() => handleAction('start_game')}>Start game</button>
      case 'finished':
        return <button onClick={() => handleAction('restart_game')}>Restart game</button>
      default:
        return null
    }
  }

  const renderCardLabel = (card: string) => {
    let buttonLabel = card
    let cardValue = card.slice(0, -1)
    let cardSuit = card[card.length - 1]

    switch (cardSuit) {
      case 'H':
        buttonLabel = `${cardValue} ♡`
        break
      case 'D':
        buttonLabel = `${cardValue} ♢`
        break
      case 'C':
        buttonLabel = `${cardValue} ♣`
        break
      case 'S':
        buttonLabel = `${cardValue} ♠`
        break
      default:
        buttonLabel = card
    }

    return buttonLabel
  }

  const renderConnectionStatus = () => {
    if (websocketRef.current) {
      return `Connected as Player ${sessionId}`
    } else {
      return 'Not connected to WebSocket server'
    }
  }

  return (
    <>
      {renderActionButtons()}
      <pre>
        <p>{renderConnectionStatus()}</p>
        <p>Players:</p>
        <ul>
          {Object.entries(players).map(([id, player]) => (
            <li key={id}>{player.name}</li>
          ))}
        </ul>
        <p>Game state</p>
        <ul>
          {gameState ? (
            <>
              <li>round: {gameState.round}</li>
              <li>status: {gameState.status}</li>
            </>
          ) : (
            <li>
              <i>No game state</i>
            </li>
          )}
        </ul>
        <p>Discard pile:</p>
        <ol>
          {gameState?.discard_pile.map((card) => (
            <li key={card}>{renderCardLabel(card)}</li>
          ))}
        </ol>
        <p>My hand:</p>
        {players &&
          players[sessionId]?.hand.map((card) => (
            <button key={card} onClick={() => handlePlayCard(card)}>
              {renderCardLabel(card)}
            </button>
          ))}
      </pre>
    </>
  )
}

export default App
