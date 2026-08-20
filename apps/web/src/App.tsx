import { useEffect, useMemo, useState } from 'react'
import { createClient } from './api/client'
import { DEMO_OWNER } from './session'
import { Home } from './pages/Home'
import { Workbench } from './pages/Workbench'
import type { Persona } from './api/types'

function useHashPersona(): string | null {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return hash.match(/^#\/personas\/([^/]+)/)?.[1] ?? null
}

export default function App() {
  const client = useMemo(() => createClient(DEMO_OWNER), [])
  const personaId = useHashPersona()
  const [personas, setPersonas] = useState<Persona[]>([])
  const [error, setError] = useState<string | undefined>()

  useEffect(() => {
    let cancelled = false
    client
      .listPersonas()
      .then((items) => {
        if (!cancelled) setPersonas(items)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [client])

  if (personaId) {
    return (
      <Workbench
        client={client}
        personaId={personaId}
        onBack={() => {
          window.location.hash = '#/'
        }}
      />
    )
  }

  return (
    <Home
      personas={personas}
      error={error}
      onOpen={(id) => {
        window.location.hash = `#/personas/${id}`
      }}
    />
  )
}
