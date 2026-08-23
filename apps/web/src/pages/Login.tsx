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
  const [email, setEmail] = useState('demo-a@arbor.eval')
  const [password, setPassword] = useState('arbor-owner')

  function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    onLogin(email.trim(), password)
  }

  return (
    <section className="home">
      <header className="home-bar">
        <h1>登录 Arbor</h1>
      </header>
      <p>用邮箱和密码换取令牌。演示账号已预填，可改成成员账号。</p>
      {error ? <p role="alert">{error}</p> : null}
      <form className="create-persona" onSubmit={submit}>
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
        <button type="submit" disabled={Boolean(busy) || !email.trim() || !password}>
          登录
        </button>
      </form>
      <p className="runtime-status">
        演示主人 demo-a@arbor.eval / arbor-owner
        <br />
        演示成员 member-a@arbor.eval / arbor-member
      </p>
    </section>
  )
}
