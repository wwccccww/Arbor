const STORAGE_PREFIX = 'arbor.thread.'

export function loadThreadSelection(personaId: string): string | null {
  try {
    return sessionStorage.getItem(`${STORAGE_PREFIX}${personaId}`)
  } catch {
    return null
  }
}

export function saveThreadSelection(personaId: string, threadId: string): void {
  try {
    sessionStorage.setItem(`${STORAGE_PREFIX}${personaId}`, threadId)
  } catch {
    // Ignore quota / private-mode failures; selection just won't persist.
  }
}
