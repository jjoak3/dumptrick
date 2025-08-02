import { useState, useEffect, useRef } from 'react'

interface GameState {
  round: number
  status: string // 'waiting', 'playing', 'finished'
}

function App() {
  const [clientAddress, setClientAddress] = useState('')
  const [clientAddresses, setClientAddresses] = useState<string[]>([])
  const [connected, setConnected] = useState(false)
  const [gameState, setGameState] = useState<GameState | undefined>(undefined)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // Connect to FastAPI WebSocket server
    const ws = new WebSocket('ws://localhost:8000/ws')

    // Store WebSocket instance in ref to prevent re-creation on re-renders
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
    }

    ws.onclose = () => {
      setConnected(false)
    }

    ws.onmessage = (event) => {
      try {
        // Parse incoming data from WebSocket server
        const data = JSON.parse(event.data)
        if (data.client_address) setClientAddress(data.client_address)
        if (data.client_addresses) setClientAddresses(data.client_addresses)
        if (data.game_state) setGameState(data.game_state)
      } catch (error) {
        console.error('Error parsing message:', error)
      }
    }

    // Close WebSocket connection on component unmount
    return () => ws.close()
  }, [])

  const handleAction = (action: string) => {
    if (wsRef.current && connected) {
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
    if (clientAddress && connected) {
      return `Connected to WebSocket server as ${clientAddress}`
    } else {
      return 'Not connected to WebSocket server'
    }
  }

  return (
    <>
      {renderActionButtons()}
      <pre>
        <p>{renderConnectionStatus()}</p>
        <p>Clients:</p>
        <ul>
          {clientAddresses.map((address, index) => (
            <li key={index}>
              <code>{address}</code>
            </li>
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
