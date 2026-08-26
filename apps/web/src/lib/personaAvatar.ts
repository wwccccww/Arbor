import type { Persona } from '../api/types'

export function personaAvatar(persona: Pick<Persona, 'avatar' | 'skin' | 'display_name'>): string {
  const custom = (persona.avatar ?? '').trim()
  if (custom) return custom
  const name = (persona.display_name ?? '').trim()
  if (name) return name.slice(0, 1)
  return persona.skin === 'employee' ? '💼' : '🌿'
}

export function personaAvatarIsEmoji(value: string): boolean {
  return value.length <= 4 && /\p{Extended_Pictographic}/u.test(value)
}
