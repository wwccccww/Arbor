import { useEffect, useMemo, useState } from 'react'
import { createClient } from './api/client'
import { DEMO_OWNER } from './session'
import { AuditLogs } from './pages/AuditLogs'
import { Checkup } from './pages/Checkup'
import { Home } from './pages/Home'
import { Workbench } from './pages/Workbench'
import type { Persona, PersonaDraft, RuntimeInfo, Tenant, TenantMember } from './api/types'

function useHashRoute(): { page: 'home' | 'checkup' | 'audit' | 'workbench'; personaId?: string } {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  if (hash.startsWith('#/checkup')) return { page: 'checkup' }
  if (hash.startsWith('#/audit')) return { page: 'audit' }
  const personaId = hash.match(/^#\/personas\/([^/]+)/)?.[1]
  if (personaId) return { page: 'workbench', personaId }
  return { page: 'home' }
}

function canCreatePersonas(role?: string) {
  return role === 'owner' || role === 'admin'
}

export default function App() {
  const [session, setSession] = useState(DEMO_OWNER)
  const client = useMemo(() => createClient(session), [session])
  const route = useHashRoute()
  const [personas, setPersonas] = useState<Persona[]>([])
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [canCreate, setCanCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [members, setMembers] = useState<TenantMember[]>([])
  const [inviting, setInviting] = useState(false)
  const [email, setEmail] = useState<string | undefined>()
  const [runtime, setRuntime] = useState<RuntimeInfo | undefined>()
  const [error, setError] = useState<string | undefined>()

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [me, items, tenants] = await Promise.all([
          client.getMe(),
          client.listPersonas(),
          client.listTenants(),
        ])
        if (cancelled) return
        setEmail(me.user.email)
        setRuntime(me.runtime)
        setPersonas(items)
        setTenants(tenants)
        const current = tenants.find((tenant) => tenant.id === session.tenantId)
        const allowed = canCreatePersonas(current?.role)
        setCanCreate(allowed)
        if (allowed) {
          const listed = await client.listMembers()
          if (cancelled) return
          setMembers(listed.forbidden ? [] : listed.items)
        } else {
          setMembers([])
        }
      } catch (err) {
        if (!cancelled) setError((err as Error).message)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [client, session.tenantId])

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

  async function createTenant(name: string) {
    setCreating(true)
    setError(undefined)
    try {
      const created = await client.createTenant(name)
      setTenants((current) => [...current, created])
      setSession((current) => ({ ...current, tenantId: created.id }))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

  async function deleteTenant() {
    setCreating(true)
    setError(undefined)
    try {
      await client.deleteTenant(session.tenantId)
      const remaining = tenants.filter((tenant) => tenant.id !== session.tenantId)
      setTenants(remaining)
      const fallback = remaining[0]?.id ?? DEMO_OWNER.tenantId
      setSession((current) => ({ ...current, tenantId: fallback }))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

  async function inviteMember(email: string, role: string) {
    setInviting(true)
    setError(undefined)
    try {
      const added = await client.addMember(email, role)
      setMembers((current) => [...current, added])
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setInviting(false)
    }
  }

  async function changeMemberRole(userId: string, role: string) {
    setInviting(true)
    setError(undefined)
    try {
      const updated = await client.patchMember(userId, role)
      setMembers((current) =>
        current.map((member) => (member.user.id === userId ? { ...member, role: updated.role } : member)),
      )
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setInviting(false)
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

  if (route.page === 'audit') {
    return (
      <AuditLogs
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
      email={email}
      runtime={runtime}
      error={error}
      canCreate={canCreate}
      creating={creating}
      members={members}
      tenants={tenants}
      currentTenantId={session.tenantId}
      canDeleteTenant={
        Boolean(tenants.find((tenant) => tenant.id === session.tenantId)?.role === 'owner') &&
        personas.length === 0
      }
      inviting={inviting}
      onOpen={(id) => {
        window.location.hash = `#/personas/${id}`
      }}
      onCheckup={() => {
        window.location.hash = '#/checkup'
      }}
      onAudit={() => {
        window.location.hash = '#/audit'
      }}
      onCreate={(draft) => void createPersona(draft)}
      onInvite={(email, role) => void inviteMember(email, role)}
      onChangeRole={(userId, role) => void changeMemberRole(userId, role)}
      onSwitchTenant={(tenantId) => {
        window.location.hash = '#/'
        setSession((current) => ({ ...current, tenantId }))
      }}
      onCreateTenant={(name) => void createTenant(name)}
      onDeleteTenant={() => void deleteTenant()}
    />
  )
}
