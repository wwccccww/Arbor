import { useState, type FormEvent } from 'react'

export function Login({
  busy,
  error,
  onLogin,
}: {
  busy?: boolean
  error?: string
  onLogin: (email: string, password: string) => void
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    onLogin(email.trim(), password)
  }

  return (
    <div className="login-shell">
      <main className="login-card">
        <header className="login-brand">
          <h1>Arbor</h1>
          <p className="eyebrow">人格树工作台</p>
        </header>
        <p>用邮箱和密码换取令牌。下方为演示账号，可直接复制使用。</p>
        {error ? <p role="alert">{error}</p> : null}
        <form onSubmit={submit}>
          <label>
            邮箱
            <input
              type="email"
              value={email}
              autoComplete="username"
              disabled={Boolean(busy)}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label>
            密码
            <input
              type="password"
              value={password}
              autoComplete="current-password"
              disabled={Boolean(busy)}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <button type="submit" className="btn--primary" disabled={Boolean(busy) || !email.trim() || !password}>
            登录
          </button>
        </form>
        <div className="login-demo">
          <p>
            演示主人 <code>demo-a@arbor.eval</code> / <code>arbor-owner</code>
          </p>
          <p>
            演示成员 <code>member-a@arbor.eval</code> / <code>arbor-member</code>
          </p>
        </div>
      </main>
    </div>
  )
}
