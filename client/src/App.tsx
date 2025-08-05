import { useState, useEffect, useRef } from 'react'

interface GameState {
  round: number
  status: string // 'waiting', 'playing', 'finished'
}

function App() {
  const [gameState, setGameState] = useState<GameState | undefined>(undefined)
  const [players, setPlayers] = useState<string[]>([])
  const [sessionId, setSessionId] = useState('')
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // Get session ID from localStorage
    let storedSessionId = localStorage.getItem('session_id')

    // Build WebSocket URL
    // If session ID exists, append as query param
    const wsUrl = 'ws://localhost:8000/ws' + (storedSessionId ? `?session_id=${storedSessionId}` : '')

    // Connect to FastAPI WebSocket server
    const ws = new WebSocket(wsUrl)

    // Store WebSocket instance in ref to prevent re-creation on re-renders
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.game_state) {
          setGameState(data.game_state)
        }

        if (data.players) {
          setPlayers(data.players)
        }

        if (data.session_id) {
          setSessionId(data.session_id)
          localStorage.setItem('session_id', data.session_id)
        }
      } catch (error) {
        console.error('Error parsing message:', error)
      }
    }

    // Close WebSocket connection when component unmounts
    return () => ws.close()
  }, [])

  const handleAction = (action: string) => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ action }))
    }
  }

  const renderActionButtons = () => {
    switch (gameState?.status) {
      case 'waiting':
        return <button onClick={() => handleAction('start_game')}>Start game</button>
      case 'playing':
        return <button onClick={() => handleAction('next_round')}>Next round</button>
      case 'finished':
        return <button onClick={() => handleAction('restart_game')}>Restart game</button>
      default:
        return null
    }
  }

  const renderConnectionStatus = () => {
    if (wsRef.current) {
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
          {players.map((name, index) => (
            <li key={index}>{name}</li>
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
      </pre>
    </>
  )
}

export default App
