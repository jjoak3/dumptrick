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
  is_winner: boolean
  name: string
  scores: number[]
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
    const websocketUrl = `ws://${import.meta.env.VITE_HOST_SERVER}:8000/ws` + (storedSessionId ? `?session_id=${storedSessionId}` : '')
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
        {gameState && players && <Scoreboard gameState={gameState} players={players} />}
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
  gameState: GameState
  players: Record<string, Player>
}

function Scoreboard({ gameState, players }: ScoreboardProps) {
  return (
    <table className='scoreboard'>
      <thead>
        <tr>
          <th></th>
          <th></th>
          <th>r1</th>
          <th>r2</th>
          <th>r3</th>
          <th>r4</th>
          <th>r5</th>
          <th>r6</th>
          <th>Total</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(players).map(([id, player]) => (
          <tr key={id}>
            <td>{player.session_id == gameState.turn_player ? '*' : ' '}</td>
            <td>
              {player.is_winner && '👑 '}
              {player.name}
            </td>
            <td>{player.scores[0]}</td>
            <td>{player.scores[1]}</td>
            <td>{player.scores[2]}</td>
            <td>{player.scores[3]}</td>
            <td>{player.scores[4]}</td>
            <td>{player.scores[5]}</td>
            <td>{player.scores.reduce((a, b) => a + b, 0)}</td>
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
  useEffect(() => {
    const topTrick = document.querySelector('.tricks > .trick:nth-last-child(1)')
    topTrick?.classList.remove('top-trick')
  })

  return (
    <div className='tricks'>
      {tricks.map((trick, index) => (
        <button className={`trick ${index === tricks.length - 1 ? 'top-trick' : ''}`} key={index}>
          {trick.cards.map((card, cardIndex) => (
            <Card //
              card={card}
              key={cardIndex}
              style={{ top: `-${index * 0.5}px` }}
            />
          ))}
        </button>
      ))}
    </div>
  )
}

interface DiscardPile {
  gameState: GameState
}

function DiscardPile({ gameState }: DiscardPile) {
  useEffect(() => {
    const topCard = document.querySelector('.discard-pile > .card:nth-last-child(1)')
    topCard?.classList.remove('top-card')
  })

  const renderDiscardPile = () => {
    if (gameState.discard_pile.length == 0) {
      return <div className='discard-pile'></div>
    }

    return (
      <button className='discard-pile'>
        {gameState.discard_pile.map((card, index) => (
          <Card //
            card={card}
            className={index === gameState.discard_pile.length - 1 ? 'top-card' : ''}
            key={card}
            style={{ top: `-${index * 0.5}px` }}
          />
        ))}
      </button>
    )
  }

  return renderDiscardPile()
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
  className?: string
  disabled?: boolean
  onClick?: () => void
  style?: React.CSSProperties
}

function Card({ card, className, disabled, onClick, style }: Card) {
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
      <div className={`card ${className}`}>{renderCardLabel(card)}</div>
    </button>
  ) : (
    <div className={`card ${className}`} style={style}>
      {renderCardLabel(card)}
    </div>
  )
}
