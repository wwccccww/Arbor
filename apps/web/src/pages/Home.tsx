import type { Persona, PersonaDraft, TenantMember } from '../api/types'
import { CreatePersonaPane } from '../components/CreatePersonaPane'
import { InviteMemberPane } from '../components/InviteMemberPane'

export function Home({
  personas,
  members,
  error,
  canCreate,
  creating,
  inviting,
  onOpen,
  onCheckup,
  onAudit,
  onCreate,
  onInvite,
  onChangeRole,
}: {
  personas: Persona[]
  members?: TenantMember[]
  error?: string
  canCreate?: boolean
  creating?: boolean
  inviting?: boolean
  onOpen: (personaId: string) => void
  onCheckup: () => void
  onAudit?: () => void
  onCreate?: (draft: PersonaDraft) => void
  onInvite?: (email: string, role: string) => void
  onChangeRole?: (userId: string, role: string) => void
}) {
  return (
    <section className="home">
      <header className="home-bar">
        <h1>工作空间</h1>
        <button type="button" onClick={onCheckup}>
          记忆体检
        </button>
        {onAudit ? (
          <button type="button" onClick={onAudit}>
            审计日志
          </button>
        ) : null}
      </header>
      {error ? <p role="alert">{error}</p> : null}
      {canCreate && onCreate ? (
        <CreatePersonaPane busy={creating} onCreate={onCreate} />
      ) : null}
      {canCreate && onInvite ? (
        <InviteMemberPane
          members={members ?? []}
          busy={inviting}
          onInvite={onInvite}
          onChangeRole={onChangeRole}
        />
      ) : null}
      <ul className="persona-grid">
        {personas.map((persona) => (
          <li key={persona.id}>
            <button type="button" onClick={() => onOpen(persona.id)}>
              <span className="eyebrow">{persona.skin === 'employee' ? '数字员工' : '陪伴'}</span>
              <strong>{persona.display_name}</strong>
              <span>{persona.one_liner}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
