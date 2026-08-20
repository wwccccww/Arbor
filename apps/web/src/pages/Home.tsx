import type { Persona } from '../api/types'

export function Home({
  personas,
  error,
  onOpen,
}: {
  personas: Persona[]
  error?: string
  onOpen: (personaId: string) => void
}) {
  return (
    <section className="home">
      <h1>工作空间</h1>
      {error ? <p role="alert">{error}</p> : null}
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
