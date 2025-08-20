import { useState, useEffect, useRef } from 'react'
import './App.css'

interface GameState {
  deck: string[]
  discard_pile: string[]
  game_phase: string
  round: number
  turn_index: number
  turn_order: string[]
  turn_player: string
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

  const handleAction = (action: string, card?: string) => {
    if (websocketRef.current) {
      websocketRef.current.send(JSON.stringify({ action, card }))
    }
  }

  const renderConnectionStatus = () => {
    if (websocketRef.current) {
      return `Connected as Player ${sessionId}`
    } else {
      return 'Not connected to WebSocket server'
    }
  }

  const renderStartButton = () => {
    switch (gameState?.game_phase) {
      case 'WAITING':
        return <button onClick={() => handleAction('start_game')}>Start game</button>
      default:
        return null
    }
  }

  return (
    <>
      <pre>
        {renderStartButton()}
        <p>{renderConnectionStatus()}</p>
        <p>Players:</p>
        {players && (
          <ul>
            {Object.entries(players).map(([id, player]) => (
              <li key={id}>{player.name}</li>
            ))}
          </ul>
        )}
        <p>Game state:</p>
        {gameState && (
          <ul>
            <li>game_phase: {gameState.game_phase}</li>
            <li>turn: Player {gameState.turn_player}</li>
          </ul>
        )}
        <p>Discard pile:</p>
        {gameState && (
          <DiscardPile //
            gameState={gameState}
          />
        )}
        <p>My hand:</p>
        {gameState && players && players[sessionId] && (
          <Hand //
            gameState={gameState}
            handleAction={handleAction}
            player={players[sessionId]}
          />
        )}
      </pre>
    </>
  )
}

export default App

interface DiscardPile {
  gameState: GameState
}

function DiscardPile({ gameState }: DiscardPile) {
  return (
    <div className='discard-pile'>
      {gameState.discard_pile.map((card, index) => (
        <Card //
          card={card}
          key={card}
          style={{ top: `-${index * 0.5}px` }}
        />
      ))}
    </div>
  )
}

interface HandProps {
  gameState: GameState
  handleAction: (action: string, card?: string) => void
  player: Player
}

function Hand({ gameState, handleAction, player }: HandProps) {
  return (
    <div className='hand'>
      {player.hand.map((card) => (
        <Card //
          card={card}
          disabled={gameState.turn_player != player.session_id}
          key={card}
          onClick={() => {
            if (gameState.turn_player == player.session_id) {
              handleAction('play_card', card)
            }
          }}
        />
      ))}
    </div>
  )
}

interface Card {
  card: string
  disabled?: boolean
  onClick?: () => void
  style?: React.CSSProperties
}

function Card({ card, disabled, onClick, style }: Card) {
  const renderCardLabel = (card: string) => {
    let cardValue = card.slice(0, -1)
    let cardSuit = card[card.length - 1]

    switch (cardSuit) {
      case 'H':
        cardSuit = '♥️'
        break
      case 'D':
        cardSuit = '♦️'
        break
      case 'C':
        cardSuit = '♣️'
        break
      case 'S':
        cardSuit = '♠️'
        break
      default:
    }

    return (
      <>
        <span>{cardValue}</span>
        <span>{cardSuit}</span>
      </>
    )
  }

  return onClick ? (
    <button disabled={disabled} onClick={onClick} style={style}>
      <div className='card'>{renderCardLabel(card)}</div>
    </button>
  ) : (
    <div className='card' style={style}>
      {renderCardLabel(card)}
    </div>
  )
}
