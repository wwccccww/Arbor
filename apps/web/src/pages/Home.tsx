import type { Persona, PersonaDraft, RuntimeInfo, Tenant, TenantMember } from '../api/types'
import { CreatePersonaPane } from '../components/CreatePersonaPane'
import { ImportFromChatPane } from '../components/ImportFromChatPane'
import { InviteMemberPane } from '../components/InviteMemberPane'
import { TenantPane } from '../components/TenantPane'
import { personaAvatar, personaAvatarIsEmoji } from '../lib/personaAvatar'

export function Home({
  personas,
  members,
  tenants,
  currentTenantId,
  canDeleteTenant,
  email,
  runtime,
  error,
  canCreate,
  creating,
  inviting,
  onOpen,
  onCheckup,
  onAudit,
  onCreate,
  onImportChat,
  onInvite,
  onChangeRole,
  onSwitchTenant,
  onCreateTenant,
  onDeleteTenant,
  onLogout,
}: {
  personas: Persona[]
  members?: TenantMember[]
  tenants?: Tenant[]
  currentTenantId?: string
  canDeleteTenant?: boolean
  email?: string
  runtime?: RuntimeInfo
  error?: string
  canCreate?: boolean
  creating?: boolean
  inviting?: boolean
  onOpen: (personaId: string) => void
  onCheckup: () => void
  onAudit?: () => void
  onCreate?: (draft: PersonaDraft, bootstrapFile?: File) => void
  onImportChat?: (personaId: string, file: File) => void
  onInvite?: (email: string, role: string) => void
  onChangeRole?: (userId: string, role: string) => void
  onSwitchTenant?: (tenantId: string) => void
  onCreateTenant?: (name: string) => void
  onDeleteTenant?: () => void
  onLogout?: () => void
}) {
  return (
    <section className="home">
      <header className="topbar">
        <div className="topbar__brand">
          Arbor
          <small>人格树工作台</small>
        </div>
        <div className="topbar__spacer" />
        <nav className="topbar__nav">
          <button type="button" className="btn--ghost" onClick={onCheckup}>
            记忆体检
          </button>
          {onAudit ? (
            <button type="button" className="btn--ghost" onClick={onAudit}>
              审计日志
            </button>
          ) : null}
          {email ? <span className="topbar__user">{email}</span> : null}
          {onLogout ? (
            <button type="button" className="btn--ghost" onClick={onLogout}>
              登出
            </button>
          ) : null}
        </nav>
      </header>

      <main>
        <div className="home-bar">
          <h1>工作空间</h1>
          {canCreate && onCreate ? (
            <span className="badge badge--companion">Owner / Admin</span>
          ) : null}
        </div>

        {runtime ? (
          <div className="runtime-status">
            <span>
              {runtime.llm === 'deepseek'
                ? 'DeepSeek 对话已接通'
                : '当前是脚本回复。在仓库根目录 .env 写入 DEEPSEEK_API_KEY 后重启，即可真实对话'}
            </span>
            <span aria-hidden>·</span>
            <span>
              {runtime.embed && runtime.embed !== 'fixture'
                ? `嵌入 ${runtime.embed}`
                : '嵌入仍是哈希夹具。写入 EMBEDDING_API_KEY 后才是真实检索'}
            </span>
            <span aria-hidden>·</span>
            <span>{runtime.store === 'postgres' ? 'Postgres 持久化' : '内存库（关掉 API 会丢数据）'}</span>
          </div>
        ) : null}
        {error ? <p role="alert">{error}</p> : null}

        <div className="section-grid">
          {tenants && currentTenantId && onSwitchTenant && onCreateTenant ? (
            <div className="section-card">
              <TenantPane
                tenants={tenants}
                currentId={currentTenantId}
                canDelete={canDeleteTenant}
                busy={creating}
                onSwitch={onSwitchTenant}
                onCreate={onCreateTenant}
                onDelete={onDeleteTenant}
              />
            </div>
          ) : null}
          {canCreate && onCreate ? (
            <div className="section-card">
              <CreatePersonaPane busy={creating} onCreate={onCreate} />
            </div>
          ) : null}
          {canCreate && onImportChat && personas.length > 0 ? (
            <div className="section-card">
              <ImportFromChatPane personas={personas} busy={creating} onImport={onImportChat} />
            </div>
          ) : null}
          {canCreate && onInvite ? (
            <div className="section-card">
              <InviteMemberPane
                members={members ?? []}
                busy={inviting}
                onInvite={onInvite}
                onChangeRole={onChangeRole}
              />
            </div>
          ) : null}
        </div>

        <h2>人设</h2>
        {personas.length === 0 ? (
          <p className="empty-state">还没有人设。创建一个数字人或陪伴助手，或在左侧导入资料。</p>
        ) : (
          <ul className="persona-grid">
            {personas.map((persona) => {
              const skin = persona.skin === 'employee' ? 'employee' : 'companion'
              const memoryCount = persona.stats?.memory_count ?? null
              const threadCount = persona.stats?.thread_count ?? null
              const avatar = personaAvatar(persona)
              const avatarEmoji = personaAvatarIsEmoji(avatar)
              return (
                <li key={persona.id}>
                  <button type="button" onClick={() => onOpen(persona.id)}>
                    <span className="persona-grid__head">
                      <span
                        className={`persona-grid__avatar${avatarEmoji ? ' persona-grid__avatar--emoji' : ''}`}
                        aria-hidden
                      >
                        {avatar}
                      </span>
                      <span className={`badge badge--${skin}`}>
                        {skin === 'employee' ? '数字员工' : '陪伴'}
                      </span>
                      <span className="eyebrow">{skin === 'employee' ? '数字员工' : '陪伴'}</span>
                    </span>
                    <strong>{persona.display_name}</strong>
                    <span className="persona-grid__one">{persona.one_liner || '还没写一句话介绍'}</span>
                    <span className="persona-grid__meta">
                      <span>
                        {memoryCount != null ? `${memoryCount} 条记忆` : '— 记忆'}
                        {threadCount != null ? (memoryCount != null ? ' · ' : ' · ') + `${threadCount} 段会话` : ''}
                        {persona.stats?.last_interaction
                          ? ` · 最近：${persona.stats.last_interaction}`
                          : ''}
                      </span>
                      <span className="cta">打开 →</span>
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </main>
    </section>
  )
}
