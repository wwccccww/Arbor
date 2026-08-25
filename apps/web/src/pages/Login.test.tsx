import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Login } from './Login'

describe('Login', () => {
  it('submits entered credentials', async () => {
    const user = userEvent.setup()
    const onLogin = vi.fn()
    render(<Login onLogin={onLogin} />)
    await user.type(screen.getByLabelText('邮箱'), 'demo-a@arbor.eval')
    await user.type(screen.getByLabelText('密码'), 'arbor-owner')
    await user.click(screen.getByRole('button', { name: '登录' }))
    expect(onLogin).toHaveBeenCalledWith('demo-a@arbor.eval', 'arbor-owner')
  })

  it('shows an error from failed login', () => {
    render(<Login error="bad credentials" onLogin={vi.fn()} />)
    expect(screen.getByRole('alert')).toHaveTextContent('bad credentials')
  })
})
