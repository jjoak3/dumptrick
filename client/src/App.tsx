import { useEffect, useRef, useState } from 'react'
import './App.css'

interface GameState {
  current_player_id: string
  current_round: number
  current_trick: Trick
  discard_pile: string[]
  game_phase: string
  turn_phase: string
}

interface Players {
  [player_id: string]: Player
}

interface Player {
  hand: string[]
  is_winner: boolean
  name: string
  scores: number[]
  player_id: string
  total_score: number
  tricks: Trick[]
}

interface Trick {
  cards: string[]
  leading_suit: string
}

const createWebSocket = () => {
  const storedId = localStorage.getItem('dumptrick_player_id')
  const serverHost = import.meta.env.VITE_SERVER_HOST
  let url = new URL(`ws://${serverHost}:8000/ws`)

  if (storedId) url.searchParams.set('player_id', storedId)

  return new WebSocket(url.toString())
}

function App() {
  const [gameState, setGameState] = useState<GameState | null>(null)
  const [players, setPlayers] = useState<Players>({})
  const [playerId, setPlayerId] = useState('')

  const websocketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const websocket = createWebSocket()
    websocketRef.current = websocket

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.game_state) setGameState(data.game_state)
        if (data.players) setPlayers(data.players)
        if (data.player_id) setPlayerId(data.player_id)
      } catch (error) {
        console.error(error)
      }
    }

    return () => websocket.close()
  }, [])

  useEffect(() => {
    if (gameState?.game_phase == 'NOT_STARTED') localStorage.removeItem('dumptrick_player_id')
    if (gameState?.game_phase == 'STARTED') localStorage.setItem('dumptrick_player_id', playerId)
  }, [gameState, playerId])

  const handleAction = (action: string, data?: Record<string, string>) => {
    const websocket = websocketRef.current
    const message = JSON.stringify({ action, ...data })

    if (websocket) websocket.send(message)
  }

  return (
    <>
      <div className='app'>
        <span className='logo'>🚛 dumptrick</span>
        {gameState && (
          <GameControls //
            gameState={gameState}
            handleAction={handleAction}
          />
        )}
        <hr />
        {gameState?.game_phase == 'NOT_STARTED' && players?.[playerId] && (
          <Lobby //
            handleAction={handleAction}
            players={players}
            playerId={playerId}
          />
        )}
        {gameState && gameState.game_phase != 'NOT_STARTED' && players?.[playerId] && (
          <GameBoard //
            gameState={gameState}
            handleAction={handleAction}
            players={players}
            playerId={playerId}
          />
        )}
      </div>
    </>
  )
}

export default App

interface GameControlsProps {
  gameState: GameState
  handleAction: (action: string, data?: Record<string, string>) => void
}

function GameControls({ gameState, handleAction }: GameControlsProps) {
  return (
    <p className='game-controls'>
      {gameState?.game_phase == 'NOT_STARTED' && <button onClick={() => handleAction('start_game')}>Start game</button>}
      {gameState?.game_phase == 'GAME_COMPLETE' && <button onClick={() => handleAction('reset_game')}>Reset game</button>}
    </p>
  )
}

interface LobbyProps {
  handleAction: (action: string, data?: Record<string, string>) => void
  players: Players
  playerId: string
}

function Lobby({ handleAction, players, playerId }: LobbyProps) {
  const [playerName, setPlayerName] = useState(() => players[playerId]?.name)

  useEffect(() => {
    handleAction('update_name', { name: playerName })
  }, [playerName])

  const handlePrompt = () => {
    const newName = prompt('Enter a new name:', playerName)
    if (newName) setPlayerName(newName)
  }

  const renderItem = (player: Player) => {
    if (player.player_id == playerId) {
      return (
        <>
          <span>{player.name} (You) </span>
          <button onClick={() => handlePrompt()}>Change name</button>
        </>
      )
    } else {
      return <span>{player.name}</span>
    }
  }

  return (
    <div className='lobby'>
      <p>Players:</p>
      <ol>
        {Object.values(players).map((player) => (
          <li key={player.player_id}>{renderItem(player)}</li>
        ))}
      </ol>
    </div>
  )
}

interface GameBoardProps {
  gameState: GameState
  handleAction: (action: string, data?: Record<string, string>) => void
  players: Players
  playerId: string
}

function GameBoard({ gameState, players, playerId, handleAction }: GameBoardProps) {
  return (
    <>
      <Scoreboard //
        gameState={gameState}
        players={players}
        playerId={playerId}
      />
      <Penalties //
        gameState={gameState}
      />
      <hr />
      <DiscardPile //
        gameState={gameState}
      />
      <hr />
      <p>Your hand:</p>
      <Hand //
        gameState={gameState}
        handleAction={handleAction}
        player={players[playerId]}
      />
      <p>Your tricks:</p>
      <Tricks //
        tricks={players[playerId].tricks}
      />
    </>
  )
}

interface ScoreboardProps {
  gameState: GameState
  players: Players
  playerId: string
}

function Scoreboard({ gameState, players, playerId }: ScoreboardProps) {
  const renderValue = (value: number | undefined) => {
    return value == undefined ? <span className='placeholder'>-</span> : value
  }

  return (
    <pre className='scoreboard-wrapper'>
      <table className='scoreboard'>
        <thead>
          <tr>
            <th></th>
            <th>Players</th>
            <th className='col-score'>{'   '}R1</th>
            <th className='col-score'>{'   '}R2</th>
            <th className='col-score'>{'   '}R3</th>
            <th className='col-score'>{'   '}R4</th>
            <th className='col-score'>{'   '}R5</th>
            <th className='col-score'>{'  '}TTL</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(players).map(([id, player]) => (
            <tr key={id}>
              <td>{player.player_id == gameState.current_player_id ? '* ' : '  '}</td>
              <td>
                {player.name}
                {player.player_id == playerId && ' (You)'}
                {gameState.game_phase == 'GAME_COMPLETE' && player.is_winner && ' 👑'}
              </td>
              {[0, 1, 2, 3, 4].map((roundIndex) => (
                <td className='col-score' key={roundIndex}>
                  {renderValue(player.scores[roundIndex])}
                </td>
              ))}
              <td className='col-score'>{renderValue(player.total_score)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </pre>
  )
}

interface PenaltiesProps {
  gameState: GameState
}

function Penalties({ gameState }: PenaltiesProps) {
  const penalties = [
    //
    '  +1 for every card',
    '  +10 for every heart',
    '  +25 for every queen',
    '  +50 for the king of spades',
    '  +100 for the last trick',
  ]

  return (
    <details className='penalties-wrapper'>
      <summary>Penalties ({gameState.current_round + 1})</summary>
      <ul className='penalties'>
        {penalties.slice(0, gameState.current_round + 1).map((penalty, index) => (
          <li key={index}>{penalty}</li>
        ))}
      </ul>
    </details>
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
  handleAction: (action: string, data?: Record<string, string>) => void
  player: Player
}

function Hand({ gameState, handleAction, player }: HandProps) {
  const isCardDisabled = (card: string) => {
    const leadingSuit = gameState.current_trick.leading_suit
    const cardSuit = card[card.length - 1]

    const isTurnComplete = gameState.turn_phase == 'TURN_COMPLETE'
    const isNotMyTurn = player.player_id != gameState.current_player_id
    const isNotLeadingSuit = leadingSuit && cardSuit != leadingSuit
    const isLeadingSuitInHand = player.hand.some((card) => card[card.length - 1] == leadingSuit)

    if (isTurnComplete) return true
    if (isNotMyTurn) return true
    if (isNotLeadingSuit && isLeadingSuitInHand) return true

    return false
  }

  return (
    <div className='hand'>
      {player.hand.map((card) => (
        <Card //
          card={card}
          disabled={isCardDisabled(card)}
          key={card}
          onClick={() => handleAction('play_card', { card })}
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
