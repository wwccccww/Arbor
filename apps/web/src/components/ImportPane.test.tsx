import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { createClient } from '../api/client'
import { DEMO_OWNER } from '../session'
import type { ImportJob } from '../api/types'
import { ImportPane } from './ImportPane'

describe('ImportPane', () => {
  it('uploads a file then loads the import job', async () => {
    const user = userEvent.setup()
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/imports') && init?.method === 'POST') {
        return new Response(JSON.stringify({ job_id: 'job-1', status: 'completed', inbox_created: 1 }), {
          status: 202,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.endsWith('/imports/job-1')) {
        return new Response(
          JSON.stringify({
            id: 'job-1',
            status: 'completed',
            filename: 'notes.txt',
            persona_id: '0a000000-0000-4000-a000-000000000010',
            inbox_created: 1,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        )
      }
      return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: 'not found' } }), { status: 404 })
    }) as unknown as typeof fetch
    const client = createClient(DEMO_OWNER, fetchImpl)
    const file = new File(['林夏讨厌香菜'], 'notes.txt', { type: 'text/plain' })

    function Harness() {
      const [job, setJob] = useState<ImportJob | null>(null)
      return (
        <ImportPane
          job={job}
          onImport={(picked, hint) => {
            void client.importFile('0a000000-0000-4000-a000-000000000010', picked, hint).then((created) =>
              client.getImport(created.job_id).then(setJob),
            )
          }}
        />
      )
    }

    render(<Harness />)

    await user.upload(screen.getByLabelText('导入文件'), file)
    await user.type(screen.getByLabelText('备注'), 'taboo')
    await user.click(screen.getByRole('button', { name: '导入' }))

    expect(await screen.findByText('notes.txt · completed · 1 条进收件箱')).toBeInTheDocument()
    const calls = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls
    const postCall = calls.find(
      (call) =>
        String(call[0]) === '/v1/personas/0a000000-0000-4000-a000-000000000010/imports' &&
        (call[1] as RequestInit).method === 'POST',
    )
    expect(postCall).toBeTruthy()
    const body = (postCall?.[1] as RequestInit).body as FormData
    expect((body.get('file') as File).name).toBe('notes.txt')
    expect(body.get('hint')).toBe('taboo')
    expect(new Headers((postCall?.[1] as RequestInit).headers).get('Content-Type')).toBeNull()
    const getCall = calls.find((call) => String(call[0]) === '/v1/imports/job-1')
    expect(getCall).toBeTruthy()
  })

  it('hides the importer without write_memory', () => {
    render(<ImportPane forbidden onImport={vi.fn()} />)
    expect(screen.queryByRole('button', { name: '导入' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('导入文件')).not.toBeInTheDocument()
  })
})
