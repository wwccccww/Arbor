import type { ReactNode } from 'react'

export function WorkbenchLayout({
  narrow = false,
  treeOpen = false,
  onToggleTree,
  left,
  center,
  right,
}: {
  narrow?: boolean
  treeOpen?: boolean
  onToggleTree?: () => void
  left: ReactNode
  center: ReactNode
  right: ReactNode
}) {
  const showTree = !narrow || treeOpen
  return (
    <div className={narrow ? 'workbench workbench-narrow' : 'workbench'}>
      <aside className="pane-left">{left}</aside>
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
