import { useEffect, useMemo, useState } from 'react'
import { createClient, login as loginRequest, logout as logoutRequest } from './api/client'
import { clearSession, DEMO_TENANT, loadSession, saveSession, type Session } from './session'
import { AuditLogs } from './pages/AuditLogs'
import { Checkup } from './pages/Checkup'
import { Home } from './pages/Home'
import { Login } from './pages/Login'
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
  const [session, setSession] = useState<Session | null>(() => loadSession())
  const client = useMemo(() => (session ? createClient(session) : null), [session])
  const [loginBusy, setLoginBusy] = useState(false)
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
    if (!client || !session) return
    const api = client
    const tenantId = session.tenantId
    let cancelled = false
    async function load() {
      try {
        const [me, items, tenants] = await Promise.all([
          api.getMe(),
          api.listPersonas(),
          api.listTenants(),
        ])
        if (cancelled) return
        setEmail(me.user.email)
        setRuntime(me.runtime)
        setPersonas(items)
        setTenants(tenants)
        const current = tenants.find((tenant) => tenant.id === tenantId)
        const allowed = canCreatePersonas(current?.role)
        setCanCreate(allowed)
        if (allowed) {
          const listed = await api.listMembers()
          if (cancelled) return
          setMembers(listed.forbidden ? [] : listed.items)
        } else {
          setMembers([])
        }
      } catch (err) {
        if (cancelled) return
        const status = (err as { status?: number }).status
        if (status === 401) {
          clearSession()
          setSession(null)
          return
        }
        setError((err as Error).message)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [client, session])

  async function signIn(email: string, password: string) {
    setLoginBusy(true)
    setError(undefined)
    try {
      const tokens = await loginRequest(email, password)
      const probe = createClient({ token: tokens.access_token, tenantId: DEMO_TENANT })
      const me = await probe.getMe()
      const tenantId = me.tenants?.[0]?.id ?? DEMO_TENANT
      const next = {
        token: tokens.access_token,
        refreshToken: tokens.refresh_token,
        tenantId,
      }
      saveSession(next)
      setSession(next)
      window.location.hash = '#/'
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoginBusy(false)
    }
  }

  async function signOut() {
    const refresh = session?.refreshToken
    clearSession()
    setSession(null)
    setEmail(undefined)
    setPersonas([])
    setTenants([])
    setMembers([])
    setRuntime(undefined)
    setError(undefined)
    window.location.hash = '#/'
    if (refresh) {
      try {
        await logoutRequest(refresh)
      } catch {
        /* client already signed out */
      }
    }
  }

  async function createPersona(draft: PersonaDraft) {
    if (!client) return
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
    if (!client) return
    setCreating(true)
    setError(undefined)
    try {
      const created = await client.createTenant(name)
      setTenants((current) => [...current, created])
      setSession((current) => {
        if (!current) return current
        const next = { ...current, tenantId: created.id }
        saveSession(next)
        return next
      })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

  async function deleteTenant() {
    if (!client || !session) return
    setCreating(true)
    setError(undefined)
    try {
      await client.deleteTenant(session.tenantId)
      const remaining = tenants.filter((tenant) => tenant.id !== session.tenantId)
      setTenants(remaining)
      const fallback = remaining[0]?.id ?? DEMO_TENANT
      setSession((current) => {
        if (!current) return current
        const next = { ...current, tenantId: fallback }
        saveSession(next)
        return next
      })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

  async function inviteMember(email: string, role: string) {
    if (!client) return
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
    if (!client) return
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

  if (!session || !client) {
    return <Login busy={loginBusy} error={error} onLogin={(email, password) => void signIn(email, password)} />
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
        setSession((current) => {
          if (!current) return current
          const next = { ...current, tenantId }
          saveSession(next)
          return next
        })
      }}
      onCreateTenant={(name) => void createTenant(name)}
      onDeleteTenant={() => void deleteTenant()}
      onLogout={() => void signOut()}
    />
  )
}
