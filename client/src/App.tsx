import { useState, useEffect, useRef } from 'react'
import './App.css'

interface GameState {
  deck: string[]
  discard_pile: string[]
  round: number
  status: string
  turn_index: number
  turn_order: string[]
  turn_player: string
  turn_phase: string
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
              <li>turn: Player {gameState.turn_player}</li>
              <li>turn phase: {gameState.turn_phase}</li>
            </>
          ) : (
            <li>
              <i>No game state</i>
            </li>
          )}
        </ul>
        <p>Board:</p>
        <div className='board'>
          {gameState && (
            <Deck //
              gameState={gameState}
              handleAction={handleAction}
              sessionId={sessionId}
            />
          )}
          {gameState && (
            <DiscardPile //
              gameState={gameState}
              handleAction={handleAction}
              sessionId={sessionId}
            />
          )}
        </div>
        <p>My hand:</p>
        {gameState && players && players[sessionId] && (
          <Hand //
            gameState={gameState}
            handleAction={handleAction}
            player={players[sessionId]}
            sessionId={sessionId}
          />
        )}
      </pre>
    </>
  )
}

export default App

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

interface Deck {
  gameState: GameState
  handleAction: (action: string, card?: string) => void
  sessionId: string
}

function Deck({ gameState, handleAction, sessionId }: Deck) {
  const renderDeck = () => {
    if (
      gameState.turn_player == sessionId && //
      gameState.turn_phase == 'DRAW'
    ) {
      return gameState.deck.map((card, index) =>
        index == gameState.deck.length - 1 ? (
          <button //
            className='card back'
            key={index}
            onClick={() => handleAction('draw_deck', card)}
            style={{ top: `-${index * 0.25}px` }}
          ></button>
        ) : (
          <div //
            className='card back'
            key={index}
            style={{ top: `-${index * 0.25}px` }}
          ></div>
        )
      )
    } else {
      return gameState.deck.map((card, index) => (
        <div //
          className='card back'
          key={index}
          style={{ top: `-${index * 0.25}px` }}
        ></div>
      ))
    }
  }

  return <div className='deck'>{renderDeck()}</div>
}

interface DiscardPile {
  gameState: GameState
  handleAction: (action: string, card?: string) => void
  sessionId: string
}

function DiscardPile({ gameState, handleAction, sessionId }: DiscardPile) {
  const renderDiscardPile = () => {
    if (
      gameState.turn_player == sessionId && //
      gameState.turn_phase == 'DRAW'
    ) {
      return gameState.discard_pile.map((card, index) =>
        index == gameState.discard_pile.length - 1 ? (
          <button //
            className='card'
            key={card}
            onClick={() => handleAction('draw_discard', card)}
            style={{ top: `-${index * 0.25}px` }}
          >
            {renderCardLabel(card)}
          </button>
        ) : (
          <div //
            className='card'
            key={index}
            style={{ top: `-${index * 0.25}px` }}
          >
            {renderCardLabel(card)}
          </div>
        )
      )
    } else {
      return gameState.discard_pile.map((card, index) => (
        <div //
          className='card'
          key={index}
          style={{ top: `-${index * 0.25}px` }}
        >
          {renderCardLabel(card)}
        </div>
      ))
    }
  }

  return <div className='discard-pile'>{renderDiscardPile()}</div>
}

interface HandProps {
  gameState: GameState
  handleAction: (action: string, card: string) => void
  player: Player
  sessionId: string
}

function Hand({ gameState, handleAction, player, sessionId }: HandProps) {
  const [selectedCard, setSelectedCard] = useState<string>('')

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!selectedCard) return

      switch (event.key) {
        case 'ArrowLeft':
          if (event.metaKey) {
            event.preventDefault()
            handleAction('move_card_left', selectedCard)
          }
          break
        case 'ArrowRight':
          if (event.metaKey) {
            event.preventDefault()
            handleAction('move_card_right', selectedCard)
          }
          break
        case 'Enter':
          if (
            gameState.turn_player == sessionId && //
            gameState.turn_phase == 'DISCARD'
          ) {
            handleAction('discard_card', selectedCard)
          }
          break
        case 'Escape':
          setSelectedCard('')
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleAction, selectedCard])

  return (
    <>
      <div className='hand'>
        {player.hand.map((card) => (
          <Card //
            card={card}
            key={card}
            isSelected={selectedCard === card}
            onBlur={() => setSelectedCard('')}
            onChange={() => setSelectedCard(card)}
            onFocus={() => setSelectedCard(card)}
          />
        ))}
      </div>
    </>
  )
}

interface CardProps {
  card: string
  isSelected: boolean
  onBlur?: () => void
  onChange?: () => void
  onFocus?: () => void
}

function Card({ card, isSelected, onBlur, onChange, onFocus }: CardProps) {
  return (
    <label className='card' htmlFor={card}>
      <input //
        type='radio'
        checked={isSelected}
        id={card}
        name='hand'
        onBlur={onBlur}
        onChange={onChange}
        onFocus={onFocus}
        value={card}
      />
      {renderCardLabel(card)}
    </label>
  )
}
