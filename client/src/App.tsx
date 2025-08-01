import { useState, useEffect, useRef } from 'react'

function App() {
  const [connected, setConnected] = useState(false)
  const [messages, setMessages] = useState<string[]>([])
  const [input, setInput] = useState('')
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
      setMessages((prev) => [...prev, event.data])
    }

    // Close WebSocket connection on component unmount
    return () => ws.close()
  }, [])

  const sendMessage = (event: React.FormEvent<HTMLFormElement>) => {
    event?.preventDefault()

    if (wsRef.current && connected && input) {
      wsRef.current.send(input)
      setInput('')
    }
  }

  return (
    <>
      <p>Connected to WebSocket: {connected ? 'Yes' : 'No'}</p>
      <form onSubmit={sendMessage}>
        <input onChange={(e) => setInput(e.target.value)} type='text' value={input} />
        <button type='submit'>Send</button>
      </form>
      <ul>
        {messages.map((message, id) => (
          <li key={id}>{message}</li>
        ))}
      </ul>
    </>
  )
}

export default App
