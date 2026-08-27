import { useMemo } from 'react'

export type DemoStepId = 'import' | 'inbox' | 'tree' | 'ask' | 'checkup'

const STEPS: { id: DemoStepId; title: string; detail: string }[] = [
  {
    id: 'import',
    title: '导入旧聊天',
    detail: '左侧「导入」上传文本；可用演示样例 sample-chat.txt。',
  },
  {
    id: 'inbox',
    title: '处理收件箱',
    detail: '点「一键写入记忆并建树」，或逐条「记下来」并勾选关键事件。',
  },
  {
    id: 'tree',
    title: '传记目录可见',
    detail: '右侧默认「传记目录」，应出现吵架、沉默等新节点。',
  },
  {
    id: 'ask',
    title: '提问并点引用',
    detail: '问「我们上次为什么吵架」，点击回复下的依据跳回节点。',
  },
  {
    id: 'checkup',
    title: '体检泄漏为 0',
    detail: '工作空间 → 记忆体检，跨租户泄漏须为 0。',
  },
]

export function DemoGuidePane({
  inboxCount = 0,
  eventCount = 0,
  importDone = false,
  onOpenCheckup,
}: {
  inboxCount?: number
  eventCount?: number
  importDone?: boolean
  onOpenCheckup?: () => void
}) {
  const completed = useMemo(() => {
    const done = new Set<DemoStepId>()
    if (importDone || inboxCount > 0) done.add('import')
    if (inboxCount === 0 && eventCount > 0) done.add('inbox')
    if (eventCount > 0) done.add('tree')
    return done
  }, [inboxCount, eventCount, importDone])

  return (
    <section className="demo-guide" aria-label="五分钟演示路径">
      <h3>演示路径</h3>
      <p className="form-hint">导入 → Inbox → 确认 → 传记目录 → 提问点引用 → 体检。</p>
      <p className="form-hint">
        <a href="/demo/sample-chat.txt" download="sample-chat.txt">下载演示聊天样例</a>
      </p>
      <ol className="demo-guide__steps">
        {STEPS.map((step, index) => {
          const done = completed.has(step.id)
          return (
            <li key={step.id} className="demo-guide__step" data-done={done ? 'true' : 'false'}>
              <span className={`badge ${done ? 'badge--ok' : ''}`}>{done ? '✓' : index + 1}</span>
              <div>
                <strong>{step.title}</strong>
                <p className="form-hint">{step.detail}</p>
                {step.id === 'checkup' && onOpenCheckup ? (
                  <button type="button" className="btn--ghost" onClick={onOpenCheckup}>
                    打开记忆体检
                  </button>
                ) : null}
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
