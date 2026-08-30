import { useEffect, useMemo, useRef, useState } from 'react'
import { createClient, login as loginRequest, logout as logoutRequest } from './api/client'
import type { AuthTokens } from './api/types'
import { clearSession, DEMO_TENANT, loadSession, pickTenantId, saveSession, type Session } from './session'
import { AuditLogs } from './pages/AuditLogs'
import { Checkup } from './pages/Checkup'
import { DebugPage } from './pages/DebugPage'
import { Home } from './pages/Home'
import { InboxPage } from './pages/InboxPage'
import { Login } from './pages/Login'
import { Workbench } from './pages/Workbench'
import type { Persona, PersonaDraft, RuntimeInfo, Tenant, TenantMember } from './api/types'

function useHashRoute(): {
  page: 'home' | 'checkup' | 'audit' | 'workbench' | 'inbox' | 'debug'
  personaId?: string
} {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  if (hash.startsWith('#/checkup')) return { page: 'checkup' }
  if (hash.startsWith('#/audit')) return { page: 'audit' }
  if (hash.startsWith('#/debug')) return { page: 'debug' }
  const inboxMatch = hash.match(/^#\/personas\/([^/]+)\/inbox$/)
  if (inboxMatch) return { page: 'inbox', personaId: inboxMatch[1] }
  const personaId = hash.match(/^#\/personas\/([^/]+)/)?.[1]
  if (personaId) return { page: 'workbench', personaId }
  return { page: 'home' }
}

function canCreatePersonas(role?: string) {
  return role === 'owner' || role === 'admin'
}

export default function App() {
  const [session, setSession] = useState<Session | null>(() => loadSession())
  const sessionRef = useRef(session)
  sessionRef.current = session

  const client = useMemo(() => {
    if (!session) return null
    const live = { ...session }
    return createClient(live, fetch, {
      onTokensRefreshed: (tokens: AuthTokens) => {
        const next = {
          token: tokens.access_token,
          refreshToken: tokens.refresh_token,
          tenantId: sessionRef.current?.tenantId ?? DEMO_TENANT,
        }
        saveSession(next)
        setSession(next)
      },
      onUnauthorized: () => {
        clearSession()
        setSession(null)
        window.location.hash = '#/'
      },
    })
  }, [session])

  const [loginBusy, setLoginBusy] = useState(false)
  const route = useHashRoute()
  const [personas, setPersonas] = useState<Persona[]>([])
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [canCreate, setCanCreate] = useState(false)
  const [creatingPersona, setCreatingPersona] = useState(false)
  const [importingChat, setImportingChat] = useState(false)
  const [creatingTenant, setCreatingTenant] = useState(false)
  const [deletingTenant, setDeletingTenant] = useState(false)
  const [members, setMembers] = useState<TenantMember[]>([])
  const [inviting, setInviting] = useState(false)
  const [changingRole, setChangingRole] = useState(false)
  const [email, setEmail] = useState<string | undefined>()
  const [runtime, setRuntime] = useState<RuntimeInfo | undefined>()
  const [error, setError] = useState<string | undefined>()
  const [feishuNotice, setFeishuNotice] = useState<string | undefined>()

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const feishu = params.get('feishu')
    if (!feishu) return
    if (feishu === 'connected') {
      setFeishuNotice('飞书日历已绑定成功')
    } else if (feishu === 'error') {
      setFeishuNotice('飞书绑定失败，请重试')
    }
    params.delete('feishu')
    params.delete('code')
    params.delete('msg')
    params.delete('reason')
    const query = params.toString()
    const next = `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`
    window.history.replaceState(null, '', next)
  }, [])

  useEffect(() => {
    if (!client || !session) return
    const api = client
    const tenantId = session.tenantId
    let cancelled = false

    async function load() {
      try {
        const [me, items, listedTenants] = await Promise.all([
          api.getMe(),
          api.listPersonas({ includeStats: true }),
          api.listTenants(),
        ])
        if (cancelled) return
        setEmail(me.user.email)
        setRuntime(me.runtime)
        setPersonas(items)
        setTenants(listedTenants)
        const current = listedTenants.find((tenant) => tenant.id === tenantId)
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
      const previous = loadSession()
      const probe = createClient({ token: tokens.access_token, tenantId: DEMO_TENANT })
      const me = await probe.getMe()
      const tenantId = pickTenantId(me.tenants, previous?.tenantId, DEMO_TENANT)
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

  async function createPersona(draft: PersonaDraft, bootstrapFile?: File) {
    if (!client) return
    setCreatingPersona(true)
    setError(undefined)
    try {
      const created = await client.createPersona(draft)
      if (bootstrapFile) {
        const imported = await client.importFile(created.id, bootstrapFile, '从创建向导导入')
        await client.pollImport(imported.job_id)
        await client.bootstrapInbox(created.id)
      }
      setPersonas((current) => [...current, created])
      window.location.hash = `#/personas/${created.id}`
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setCreatingPersona(false)
    }
  }

  async function importChatToPersona(personaId: string, file: File) {
    if (!client) return
    setImportingChat(true)
    setError(undefined)
    try {
      const imported = await client.importFile(personaId, file, '从首页聊天导入')
      await client.pollImport(imported.job_id)
      await client.bootstrapInbox(personaId)
      const refreshed = await client.listPersonas()
      setPersonas(refreshed)
      window.location.hash = `#/personas/${personaId}`
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setImportingChat(false)
    }
  }

  async function createTenant(name: string) {
    if (!client) return
    setCreatingTenant(true)
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
      setCreatingTenant(false)
    }
  }

  async function deleteTenant() {
    if (!client || !session) return
    setDeletingTenant(true)
    setError(undefined)
    try {
      await client.deleteTenant(session.tenantId)
      const remaining = tenants.filter((tenant) => tenant.id !== session.tenantId)
      setTenants(remaining)
      const fallback = pickTenantId(remaining, undefined, DEMO_TENANT)
      setSession((current) => {
        if (!current) return current
        const next = { ...current, tenantId: fallback }
        saveSession(next)
        return next
      })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setDeletingTenant(false)
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
    setChangingRole(true)
    setError(undefined)
    try {
      const updated = await client.patchMember(userId, role)
      setMembers((current) =>
        current.map((member) => (member.user.id === userId ? { ...member, role: updated.role } : member)),
      )
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setChangingRole(false)
    }
  }

  if (!session || !client) {
    return <Login busy={loginBusy} error={error} onLogin={(email, password) => void signIn(email, password)} />
  }

  const currentTenant = tenants.find((tenant) => tenant.id === session.tenantId)
  const workspaceAdmin = canCreatePersonas(currentTenant?.role)

  if (route.page === 'inbox' && route.personaId) {
    return (
      <InboxPage
        client={client}
        personaId={route.personaId}
        onBack={() => {
          window.location.hash = '#/'
        }}
        onOpenWorkbench={() => {
          window.location.hash = `#/personas/${route.personaId}`
        }}
      />
    )
  }

  if (route.page === 'workbench' && route.personaId) {
    return (
      <Workbench
        client={client}
        personaId={route.personaId}
        workspaceAdmin={workspaceAdmin}
        feishuEnabled={runtime?.feishu === 'feishu'}
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
        personas={personas.map((p) => ({ id: p.id, display_name: p.display_name }))}
        onBack={() => {
          window.location.hash = '#/'
        }}
      />
    )
  }

  if (route.page === 'debug') {
    return (
      <DebugPage
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
      notice={feishuNotice}
      canCreate={canCreate}
      creating={creatingPersona || creatingTenant || deletingTenant || importingChat}
      members={members}
      tenants={tenants}
      currentTenantId={session.tenantId}
      canDeleteTenant={
        Boolean(currentTenant?.role === 'owner') && personas.length === 0
      }
      inviting={inviting || changingRole}
      onOpen={(id) => {
        window.location.hash = `#/personas/${id}`
      }}
      onOpenInbox={(id) => {
        window.location.hash = `#/personas/${id}/inbox`
      }}
      onCheckup={() => {
        window.location.hash = '#/checkup'
      }}
      onAudit={() => {
        window.location.hash = '#/audit'
      }}
      onDebug={() => {
        window.location.hash = '#/debug'
      }}
      onCreate={(draft, bootstrapFile) => void createPersona(draft, bootstrapFile)}
      onImportChat={(personaId, file) => void importChatToPersona(personaId, file)}
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
