import { useEffect, useMemo, useState } from 'react'
import { createClient } from './api/client'
import { DEMO_OWNER } from './session'
import { Checkup } from './pages/Checkup'
import { Home } from './pages/Home'
import { Workbench } from './pages/Workbench'
import type { Persona, PersonaDraft } from './api/types'

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

function canCreatePersonas(role?: string) {
  return role === 'owner' || role === 'admin'
}

export default function App() {
  const client = useMemo(() => createClient(DEMO_OWNER), [])
  const route = useHashRoute()
  const [personas, setPersonas] = useState<Persona[]>([])
  const [canCreate, setCanCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | undefined>()

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [items, tenants] = await Promise.all([client.listPersonas(), client.listTenants()])
        if (cancelled) return
        setPersonas(items)
        const current = tenants.find((tenant) => tenant.id === DEMO_OWNER.tenantId)
        setCanCreate(canCreatePersonas(current?.role))
      } catch (err) {
        if (!cancelled) setError((err as Error).message)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [client])

  async function createPersona(draft: PersonaDraft) {
    setCreating(true)
    setError(undefined)
    try {
      const created = await client.createPersona(draft)
      setPersonas((current) => [...current, created])
      window.location.hash = `#/personas/${created.id}`
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

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
      canCreate={canCreate}
      creating={creating}
      onOpen={(id) => {
        window.location.hash = `#/personas/${id}`
      }}
      onCheckup={() => {
        window.location.hash = '#/checkup'
      }}
      onCreate={(draft) => void createPersona(draft)}
    />
  )
}
