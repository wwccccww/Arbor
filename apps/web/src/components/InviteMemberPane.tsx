import { useState, type FormEvent } from 'react'
import type { TenantMember } from '../api/types'

export function InviteMemberPane({
  members,
  forbidden,
  busy,
  onInvite,
  onChangeRole,
}: {
  members: TenantMember[]
  forbidden?: boolean
  busy?: boolean
  onInvite: (email: string, role: string) => void
  onChangeRole?: (userId: string, role: string) => void
}) {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('member')

  if (forbidden) return null

  function submit(event: FormEvent) {
    event.preventDefault()
    const address = email.trim()
    if (!address || busy) return
    onInvite(address, role)
    setEmail('')
    setRole('member')
  }

  return (
    <section className="create-persona">
      <h2>空间成员</h2>
      <p>邀请进工作空间后，还要在人设里单独授权。</p>
      {members.length ? (
        <ul className="member-list">
          {members.map((member) => (
            <li key={member.user.id}>
              <span>
                {member.user.email} · {member.role}
              </span>
              {member.role === 'owner' || !onChangeRole ? null : (
                <label>
                  {member.user.email} 角色
                  <select
                    value={member.role}
                    disabled={Boolean(busy)}
                    onChange={(event) => onChangeRole(member.user.id, event.target.value)}
                  >
                    <option value="member">成员</option>
                    <option value="admin">管理员</option>
                  </select>
                </label>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p>还没有成员</p>
      )}
      <form onSubmit={submit}>
        <label>
          邮箱
          <input
            type="email"
            value={email}
            disabled={Boolean(busy)}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label>
          角色
          <select value={role} disabled={Boolean(busy)} onChange={(event) => setRole(event.target.value)}>
            <option value="member">成员</option>
            <option value="admin">管理员</option>
          </select>
        </label>
        <button type="submit" disabled={Boolean(busy) || !email.trim()}>
          邀请
        </button>
      </form>
    </section>
  )
}
