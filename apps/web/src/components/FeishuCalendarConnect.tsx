import { useCallback, useEffect, useState } from 'react'
import type { ArborClient } from '../api/client'
import type { FeishuCalendarStatus } from '../api/types'

export function FeishuCalendarConnect({
  client,
  editable,
}: {
  client: ArborClient
  editable?: boolean
}) {
  const [status, setStatus] = useState<FeishuCalendarStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const next = await client.getFeishuCalendarStatus()
      setStatus(next)
      setError(null)
    } catch (err) {
      setError((err as Error).message)
    }
  }, [client])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    const onFocus = () => void refresh()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [refresh])

  async function connect() {
    setBusy(true)
    setError(null)
    try {
      const { authorize_url } = await client.getFeishuConnectUrl()
      window.location.href = authorize_url
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }

  async function disconnect() {
    setBusy(true)
    setError(null)
    try {
      await client.disconnectFeishu()
      await refresh()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const connected = Boolean(status?.connected)

  return (
    <section className="feishu-connect" aria-label="飞书日历">
      <h3>飞书日历</h3>
      <p className="muted">
        绑定后，人设开启 <code>calendar</code> 工具时可查询你的飞书日程。
      </p>
      {error ? (
        <p className="workbench-alert" role="alert">{error}</p>
      ) : null}
      <p>
        状态：
        {status === null ? '检查中…' : connected ? '已连接' : '未连接'}
      </p>
      {editable ? (
        <div className="feishu-connect__actions">
          {connected ? (
            <button type="button" disabled={busy} onClick={() => void disconnect()}>
              解除绑定
            </button>
          ) : (
            <button type="button" disabled={busy} onClick={() => void connect()}>
              连接飞书日历
            </button>
          )}
        </div>
      ) : null}
    </section>
  )
}
