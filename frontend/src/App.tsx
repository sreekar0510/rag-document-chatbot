import { useEffect, useState } from 'react'
import './App.css'

interface HealthStatus {
  status: string
  version: string
  timestamp: string
}

function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json() as Promise<HealthStatus>
      })
      .then(setHealth)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Unknown error')
      })
  }, [])

  return (
    <div className="app">
      <header className="app-header">
        <h1>RAG Document Chatbot</h1>
        <p className="subtitle">AI-powered document Q&amp;A</p>
      </header>

      <main className="app-main">
        <section className="status-card">
          <h2>Backend Status</h2>
          {health && (
            <div className="status-ok">
              <span className="badge badge-ok">● {health.status.toUpperCase()}</span>
              <p>Version: <strong>{health.version}</strong></p>
              <p>Checked: <time>{health.timestamp}</time></p>
            </div>
          )}
          {error && (
            <div className="status-error">
              <span className="badge badge-error">● UNREACHABLE</span>
              <p>{error}</p>
              <p className="hint">Ensure the FastAPI backend is running on port 8000.</p>
            </div>
          )}
          {!health && !error && <p className="loading">Checking…</p>}
        </section>

        <section className="coming-soon">
          <h2>Coming soon</h2>
          <ul>
            <li>📄 PDF &amp; TXT document upload</li>
            <li>🔍 Semantic search &amp; retrieval</li>
            <li>💬 AI-powered chat with source citations</li>
          </ul>
        </section>
      </main>
    </div>
  )
}

export default App
