import { afterEach, describe, expect, it } from 'vitest'

import { loadThreadSelection, saveThreadSelection } from './threadSelection'

describe('threadSelection', () => {
  afterEach(() => {
    sessionStorage.clear()
  })

  it('remembers the active thread for a persona', () => {
    saveThreadSelection('persona-a', 'thread-2')
    expect(loadThreadSelection('persona-a')).toBe('thread-2')
    expect(loadThreadSelection('persona-b')).toBeNull()
  })
})
