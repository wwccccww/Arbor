export type Session = {
  token: string
  refreshToken?: string
  tenantId: string
}

export const DEMO_TENANT = '0a000000-0000-4000-a000-000000000001'

export const DEMO_OWNER: Session = {
  token: 'token-a',
  tenantId: DEMO_TENANT,
}

export const DEMO_MEMBER: Session = {
  token: 'token-member',
  tenantId: DEMO_TENANT,
}

const STORAGE_KEY = 'arbor.session'

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Session
    if (!parsed.token || !parsed.tenantId) return null
    return parsed
  } catch {
    return null
  }
}

export function saveSession(session: Session): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
}

export function clearSession(): void {
  localStorage.removeItem(STORAGE_KEY)
}

export function pickTenantId(
  tenants: { id: string }[] | undefined,
  preferredId?: string,
  fallback = DEMO_TENANT,
): string {
  if (preferredId && tenants?.some((tenant) => tenant.id === preferredId)) return preferredId
  return tenants?.[0]?.id ?? fallback
}
