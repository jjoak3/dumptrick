import { useState, useEffect, useRef } from 'react'
import './App.css'

interface Trick {
  cards: string[]
  leading_suit: string
  winning_card: string
  winning_player: string
}

interface GameState {
  current_trick: Trick
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
  tricks: Trick[]
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
        <p>Scoreboard:</p>
        {players && <Scoreboard players={players} />}
        <p>Game state:</p>
        {gameState && (
          <ul>
            <li>game_phase: {gameState.game_phase}</li>
            <li>turn_index: {gameState.turn_index}</li>
            <li>turn: {gameState.turn_player}</li>
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
        <p>My tricks:</p>
        {gameState && players && players[sessionId] && (
          <Tricks //
            tricks={players[sessionId].tricks}
          />
        )}
      </pre>
    </>
  )
}

export default App

interface ScoreboardProps {
  players: Record<string, Player>
}

function Scoreboard({ players }: ScoreboardProps) {
  return (
    <table className='scoreboard'>
      <thead>
        <tr>
          <th>Player</th>
          <th>Tricks</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(players).map(([id, player]) => (
          <tr key={id}>
            <td>{player.name}</td>
            <td>{player.tricks.length}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

interface TricksProps {
  tricks: Trick[]
}

function Tricks({ tricks }: TricksProps) {
  return (
    <div className='tricks'>
      {tricks.map((trick, index) => (
        <div className='trick' key={index}>
          {trick.cards.map((card, cardIndex) => (
            <Card //
              card={card}
              key={cardIndex}
              style={{ top: `-${index * 0.5}px` }}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

interface DiscardPile {
  gameState: GameState
}

function DiscardPile({ gameState }: DiscardPile) {
  return (
    <button className='discard-pile'>
      {gameState.discard_pile.map((card, index) => (
        <Card //
          card={card}
          key={card}
          style={{ top: `-${index * 0.5}px` }}
        />
      ))}
    </button>
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
