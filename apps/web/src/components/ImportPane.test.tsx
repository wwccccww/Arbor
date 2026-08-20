import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import { ImportPane } from './ImportPane'

describe('ImportPane', () => {
  it('uploads a file to the imports API', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ job_id: 'job-1', status: 'completed', inbox_created: 1 }), {
        status: 202,
        headers: { 'Content-Type': 'application/json' },
      }),
    ) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const file = new File(['林夏讨厌香菜'], 'notes.txt', { type: 'text/plain' })

    render(
      <ImportPane
        onImport={(picked, hint) => {
          void client.importFile('0a000000-0000-4000-a000-000000000010', picked, hint)
        }}
      />,
    )

    await user.upload(screen.getByLabelText('导入文件'), file)
    await user.type(screen.getByLabelText('备注'), 'taboo')
    await user.click(screen.getByRole('button', { name: '导入' }))

    expect(fetchImpl).toHaveBeenCalled()
    const [url, init] = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/v1/personas/0a000000-0000-4000-a000-000000000010/imports')
    expect((init as RequestInit).method).toBe('POST')
    const body = (init as RequestInit).body as FormData
    expect(body).toBeInstanceOf(FormData)
    expect((body.get('file') as File).name).toBe('notes.txt')
    expect(body.get('hint')).toBe('taboo')
    const headers = new Headers((init as RequestInit).headers)
    expect(headers.get('Content-Type')).toBeNull()
    expect(headers.get('Authorization')).toBe('Bearer token-a')
  })

  it('hides the importer without write_memory', () => {
    render(<ImportPane forbidden onImport={vi.fn()} />)
    expect(screen.queryByRole('button', { name: '导入' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('导入文件')).not.toBeInTheDocument()
  })
})
