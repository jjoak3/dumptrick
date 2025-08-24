import { useEffect, useRef, useState } from 'react'
import './App.css'

interface GameState {
  discard_pile: string[]
  game_phase: string
  turn_player: string
}

interface Players {
  [session_id: string]: Player
}

interface Player {
  hand: string[]
  is_winner: boolean
  name: string
  scores: number[]
  session_id: string
  total_score: number
  tricks: Trick[]
}

interface Trick {
  cards: string[]
}

const createWebSocket = () => {
  const storedId = localStorage.getItem('session_id')
  const serverHost = import.meta.env.VITE_SERVER_HOST
  let url = new URL(`ws://${serverHost}:8000/ws`)

  if (storedId) url.searchParams.set('session_id', storedId)

  return new WebSocket(url.toString())
}

function App() {
  const [gameState, setGameState] = useState<GameState | null>(null)
  const [players, setPlayers] = useState<Players>({})
  const [sessionId, setSessionId] = useState('')

  const websocketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const websocket = createWebSocket()
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
    const websocket = websocketRef.current
    const message = JSON.stringify({ action, card })

    if (websocket) websocket.send(message)
  }

  const renderStartButton = () => {
    switch (gameState?.game_phase) {
      case 'WAITING':
        return <button onClick={() => handleAction('start_game')}>Start game</button>
      case 'GAME_OVER':
        return <button onClick={() => handleAction('restart_game')}>Restart game</button>
      default:
        return null
    }
  }

  return (
    <>
      <pre className='app'>
        <p>{renderStartButton()}</p>
        {gameState && players && (
          <Scoreboard //
            gameState={gameState}
            players={players}
            sessionId={sessionId}
          />
        )}
        <p>***</p>
        <p>Discard pile:</p>
        {gameState && (
          <DiscardPile //
            gameState={gameState}
          />
        )}
        <p>***</p>
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
  players: Players
  sessionId: string
}

function Scoreboard({ gameState, players, sessionId }: ScoreboardProps) {
  return (
    <table className='scoreboard'>
      <thead>
        <tr>
          <th></th>
          <th></th>
          <th className='col-score'>{'  '}R1</th>
          <th className='col-score'>{'  '}R2</th>
          <th className='col-score'>{'  '}R3</th>
          <th className='col-score'>{'  '}R4</th>
          <th className='col-score'>{'  '}R5</th>
          <th className='col-score'>{'  '}R6</th>
          <th className='col-score'> TTL</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(players).map(([id, player]) => (
          <tr key={id}>
            <td>{player.session_id == gameState.turn_player ? '*' : ' '}</td>
            <td>
              {player.name}
              {player.session_id == sessionId && ' (You)'}
              {gameState.game_phase == 'GAME_OVER' && player.is_winner && ' 👑'}
            </td>
            <td className='col-score'>{player.scores[0] != undefined ? player.scores[0] : '-'}</td>
            <td className='col-score'>{player.scores[1] != undefined ? player.scores[1] : '-'}</td>
            <td className='col-score'>{player.scores[2] != undefined ? player.scores[2] : '-'}</td>
            <td className='col-score'>{player.scores[3] != undefined ? player.scores[3] : '-'}</td>
            <td className='col-score'>{player.scores[4] != undefined ? player.scores[4] : '-'}</td>
            <td className='col-score'>{player.scores[5] != undefined ? player.scores[5] : '-'}</td>
            <td className='col-score'>{player.total_score != undefined ? player.total_score : '-'}</td>
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
      {tricks.map((trick, index) => {
        const isTopTrick = index === tricks.length - 1

        return (
          <Trick //
            className={isTopTrick ? 'animate' : ''}
            key={index}
            index={index}
            trick={trick}
          />
        )
      })}
    </div>
  )
}

interface TrickProps {
  className?: string
  index: number
  trick: Trick
}

function Trick({ className, index, trick }: TrickProps) {
  return (
    <button className={`trick ${className}`}>
      {trick.cards.map((card, cardIndex) => {
        const topOffset = index * 0.5

        return (
          <Card //
            card={card}
            key={cardIndex}
            style={{ top: `-${topOffset}px` }}
          />
        )
      })}
    </button>
  )
}

interface DiscardPile {
  gameState: GameState
}

function DiscardPile({ gameState }: DiscardPile) {
  if (gameState.discard_pile.length == 0) return <div className='discard-pile'></div>

  return (
    <div className='discard-pile'>
      {gameState.discard_pile.map((card, index) => {
        const isTopCard = index === gameState.discard_pile.length - 1
        const topOffset = index * 0.5

        return (
          <Card //
            card={card}
            className={isTopCard ? 'animate' : ''}
            key={card}
            style={{ top: `-${topOffset}px` }}
          />
        )
      })}
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
            if (gameState.turn_player == player.session_id) handleAction('play_card', card)
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
    let rank = card.slice(0, -1)
    let suit = card[card.length - 1]

    switch (suit) {
      case 'H':
        suit = '♥️'
        break
      case 'D':
        suit = '♦️'
        break
      case 'C':
        suit = '♣️'
        break
      case 'S':
        suit = '♠️'
        break
      default:
    }

    return (
      <>
        <span>{rank}</span>
        <span>{suit}</span>
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
