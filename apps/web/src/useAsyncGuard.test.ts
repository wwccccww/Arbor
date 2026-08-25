import { renderHook, act } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { useAsyncGuard } from './useAsyncGuard'

describe('useAsyncGuard', () => {
  it('marks older tokens as stale after begin', () => {
    const { result } = renderHook(() => useAsyncGuard())
    let first = 0
    act(() => {
      first = result.current.begin()
    })
    act(() => {
      result.current.begin()
    })
    expect(result.current.isLatest(first)).toBe(false)
  })
})
