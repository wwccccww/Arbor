import { useEffect, useMemo, useState } from 'react'
import { createClient } from './api/client'
import { DEMO_OWNER } from './session'
import { Checkup } from './pages/Checkup'
import { Home } from './pages/Home'
import { Workbench } from './pages/Workbench'
import type { Persona } from './api/types'

function useHashRoute(): { page: 'home' | 'checkup' | 'workbench'; personaId?: string } {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  if (hash.startsWith('#/checkup')) return { page: 'checkup' }
  const personaId = hash.match(/^#\/personas\/([^/]+)/)?.[1]
  if (personaId) return { page: 'workbench', personaId }
  return { page: 'home' }
}

export default function App() {
  const client = useMemo(() => createClient(DEMO_OWNER), [])
  const route = useHashRoute()
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

  if (route.page === 'workbench' && route.personaId) {
    return (
      <Workbench
        client={client}
        personaId={route.personaId}
        onBack={() => {
          window.location.hash = '#/'
        }}
      />
    )
  }

  if (route.page === 'checkup') {
    return (
      <Checkup
        client={client}
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
      onCheckup={() => {
        window.location.hash = '#/checkup'
      }}
    />
  )
}
