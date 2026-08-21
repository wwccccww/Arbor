import { useState, type FormEvent } from 'react'
import type { Tenant } from '../api/types'

export function TenantPane({
  tenants,
  currentId,
  canDelete,
  busy,
  onSwitch,
  onCreate,
  onDelete,
}: {
  tenants: Tenant[]
  currentId: string
  canDelete?: boolean
  busy?: boolean
  onSwitch: (tenantId: string) => void
  onCreate: (name: string) => void
  onDelete?: () => void
}) {
  const [name, setName] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    const label = name.trim()
    if (!label || busy) return
    onCreate(label)
    setName('')
  }

  return (
    <section className="create-persona">
      <h2>工作空间</h2>
      <p>空空间才能删除，有人设的不级联删记忆。</p>
      <ul className="tenant-list">
        {tenants.map((tenant) => (
          <li key={tenant.id}>
            <button
              type="button"
              aria-pressed={tenant.id === currentId}
              disabled={Boolean(busy) || tenant.id === currentId}
              onClick={() => onSwitch(tenant.id)}
            >
              {tenant.name || tenant.id} · {tenant.role}
            </button>
          </li>
        ))}
      </ul>
      <form onSubmit={submit}>
        <label>
          空间名
          <input value={name} disabled={Boolean(busy)} onChange={(event) => setName(event.target.value)} />
        </label>
        <button type="submit" disabled={Boolean(busy) || !name.trim()}>
          创建空间
        </button>
      </form>
      {canDelete && onDelete ? (
        <button type="button" disabled={Boolean(busy)} onClick={onDelete}>
          删除当前空间
        </button>
      ) : null}
    </section>
  )
}
