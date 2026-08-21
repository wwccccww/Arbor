import type { Persona, PersonaDraft } from '../api/types'
import { CreatePersonaPane } from '../components/CreatePersonaPane'

export function Home({
  personas,
  error,
  canCreate,
  creating,
  onOpen,
  onCheckup,
  onCreate,
}: {
  personas: Persona[]
  error?: string
  canCreate?: boolean
  creating?: boolean
  onOpen: (personaId: string) => void
  onCheckup: () => void
  onCreate?: (draft: PersonaDraft) => void
}) {
  return (
    <section className="home">
      <header className="home-bar">
        <h1>工作空间</h1>
        <button type="button" onClick={onCheckup}>
          记忆体检
        </button>
      </header>
      {error ? <p role="alert">{error}</p> : null}
      {canCreate && onCreate ? (
        <CreatePersonaPane busy={creating} onCreate={onCreate} />
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
