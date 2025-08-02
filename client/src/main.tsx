import { createRoot } from 'react-dom/client'
import App from './App.tsx'

// Temporarily disabled StrictMode to prevent double rendering
createRoot(document.getElementById('root')!).render(<App />)
