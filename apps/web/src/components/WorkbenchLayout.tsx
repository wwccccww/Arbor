import { useEffect, useState, type ReactNode } from 'react'

type LeftTab = 'profile' | 'memory' | 'tools'

export function WorkbenchLayout({
  narrow = false,
  treeOpen = false,
  onToggleTree,
  focusTools = false,
  left,
  center,
  right,
}: {
  narrow?: boolean
  treeOpen?: boolean
  onToggleTree?: () => void
  focusTools?: boolean
  left: ReactNode
  center: ReactNode
  right: ReactNode
}) {
  const [leftTab, setLeftTab] = useState<LeftTab>('profile')
  const showTree = !narrow || treeOpen

  useEffect(() => {
    if (focusTools && narrow) setLeftTab('tools')
  }, [focusTools, narrow])

  return (
    <div className={narrow ? 'workbench workbench-narrow' : 'workbench'}>
      <aside className="pane-left">
        {narrow ? (
          <div className="workbench-tabs" role="tablist" aria-label="工作台侧栏">
            <button
              type="button"
              role="tab"
              aria-selected={leftTab === 'profile'}
              className={leftTab === 'profile' ? 'is-active' : undefined}
              onClick={() => setLeftTab('profile')}
            >
              档案
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={leftTab === 'memory'}
              className={leftTab === 'memory' ? 'is-active' : undefined}
              onClick={() => setLeftTab('memory')}
            >
              记忆
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={leftTab === 'tools'}
              className={leftTab === 'tools' ? 'is-active' : undefined}
              onClick={() => setLeftTab('tools')}
            >
              授权与导入
            </button>
          </div>
        ) : null}
        <div className={narrow ? `pane-left__panel pane-left__panel--${leftTab}` : 'pane-left__panel'}>{left}</div>
      </aside>
      <main className="pane-center">
        {narrow ? (
          <button type="button" className="btn--ghost tree-toggle" onClick={onToggleTree}>
            事件树
          </button>
        ) : null}
        {center}
      </main>
      {showTree ? <aside className="pane-right">{right}</aside> : null}
    </div>
  )
}
