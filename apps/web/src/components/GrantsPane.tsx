import { useEffect, useState } from 'react'
import type { Capability, PersonaGrant, TenantMember } from '../api/types'

const CAPABILITIES: { id: Capability; label: string }[] = [
  { id: 'chat', label: '对话' },
  { id: 'read_memory', label: '读记忆' },
  { id: 'write_memory', label: '写记忆' },
  { id: 'admin', label: '管理人设' },
]

function capsFor(grants: PersonaGrant[], userId: string): Capability[] {
  return grants.find((grant) => grant.user_id === userId)?.capabilities ?? []
}

export function GrantsPane({
  members,
  grants,
  forbidden,
  busy,
  onSave,
}: {
  members: TenantMember[]
  grants: PersonaGrant[]
  forbidden?: boolean
  busy?: boolean
  onSave: (grants: PersonaGrant[]) => void
}) {
  const [draft, setDraft] = useState<Record<string, Capability[]>>({})

  useEffect(() => {
    const next: Record<string, Capability[]> = {}
    for (const member of members) {
      next[member.user.id] = [...capsFor(grants, member.user.id)]
    }
    setDraft(next)
  }, [members, grants])

  if (forbidden) return null

  function toggle(userId: string, cap: Capability, checked: boolean) {
    setDraft((current) => {
      const present = new Set(current[userId] ?? [])
      if (checked) present.add(cap)
      else present.delete(cap)
      return { ...current, [userId]: [...present] }
    })
  }

  function save() {
    if (busy) return
    onSave(
      members
        .map((member) => ({
          user_id: member.user.id,
          capabilities: draft[member.user.id] ?? [],
        }))
        .filter((grant) => grant.capabilities.length > 0),
    )
  }

  return (
    <section>
      <h3>谁能用这个人</h3>
      <p>全量覆盖。没勾任何能力的成员会失去授权。空间所有者不必写进授权表。</p>
      {members.length === 0 ? (
        <p>没有可授权的成员</p>
      ) : (
        <ul className="grants-list">
          {members.map((member) => {
            const selected = new Set(draft[member.user.id] ?? [])
            const implicit = member.role === 'owner' || member.role === 'admin'
            return (
              <li key={member.user.id}>
                <p>
                  {member.user.email} · {member.role}
                </p>
                {implicit ? <p>空间角色已包含全部能力</p> : null}
                {CAPABILITIES.map((cap) => (
                  <label key={cap.id}>
                    <input
                      type="checkbox"
                      checked={selected.has(cap.id)}
                      disabled={Boolean(busy) || implicit}
                      aria-label={`${member.user.email} ${cap.label}`}
                      onChange={(event) => toggle(member.user.id, cap.id, event.target.checked)}
                    />
                    {cap.label}
                  </label>
                ))}
              </li>
            )
          })}
        </ul>
      )}
      <button type="button" disabled={Boolean(busy)} onClick={save}>
        保存授权
      </button>
    </section>
  )
}
