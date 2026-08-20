export type Session = {
  token: string
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
