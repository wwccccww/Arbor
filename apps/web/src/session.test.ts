import { describe, expect, it } from 'vitest'

import { DEMO_TENANT, pickTenantId } from './session'

describe('pickTenantId', () => {
  it('prefers a saved tenant when still available', () => {
    const tenants = [
      { id: 't-1' },
      { id: 't-2' },
    ]
    expect(pickTenantId(tenants, 't-2', DEMO_TENANT)).toBe('t-2')
  })

  it('falls back to the first tenant', () => {
    expect(pickTenantId([{ id: 't-1' }], 'missing', DEMO_TENANT)).toBe('t-1')
  })
})
