import { useState, useEffect, useRef } from 'react'

function App() {
  const [clientAddress, setClientAddress] = useState('')
  const [clientAddresses, setClientAddresses] = useState<string[]>([])
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
      try {
        // Parse incoming data from WebSocket server
        const data = JSON.parse(event.data)
        if (data.client_address) setClientAddress(data.client_address)
        if (data.client_addresses) setClientAddresses(data.client_addresses)
        if (data.message) setMessages((prevMessages) => [...prevMessages, data.message])
      } catch (error) {
        console.error('Error parsing message:', error)
      }
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
      <form onSubmit={sendMessage}>
        <input onChange={(e) => setInput(e.target.value)} type='text' value={input} />
        <button type='submit'>Send</button>
      </form>
      <pre>
        <p>{clientAddress && connected ? `Connected to WebSocket server as ${clientAddress}` : 'Not connected to WebSocket server'}</p>
        <p>Clients:</p>
        <ol>
          {clientAddresses.map((clientAddress, index) => (
            <li key={index}>
              <code>{clientAddress}</code>
            </li>
          ))}
        </ol>
        <p>Messages:</p>
        <ul>
          {messages.map((message, id) => (
            <li key={id}>
              {clientAddress}: {message}
            </li>
          ))}
        </ul>
      </pre>
    </>
  )
}

export default App
