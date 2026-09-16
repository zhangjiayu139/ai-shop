import { describe, expect, it, vi } from 'vitest'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { localPreviewApi } from './local-preview'

describe('local visual preview isolation', () => {
  function serve(url: string) {
    let body = ''
    const response = { statusCode: 200, setHeader: vi.fn(), end: (value: string) => { body = value } }
    const next = vi.fn()
    localPreviewApi({ url } as IncomingMessage, response as unknown as ServerResponse, next)
    return { response, body, next }
  }
  it('allows static assets to reach Vite', () => {
    expect(serve('/src/main.ts').next).toHaveBeenCalledOnce()
  })
  it('supplies only site branding and setup status', () => {
    expect(JSON.parse(serve('/api/v1/public/site').body).brand_name).toBe('TaoAi CDK自助充值')
    expect(JSON.parse(serve('/api/v1/setup/status').body).installed).toBe(true)
  })
  it.each(['/api/v1/public/cdk/preview', '/api/v1/public/cdk/preflight', '/api/v1/public/cdk/redeem', '/api/v1/admin/users'])('blocks %s without forwarding', path => {
    const { response, body, next } = serve(path)
    expect(response.statusCode).toBe(503)
    expect(next).not.toHaveBeenCalled()
    expect(JSON.parse(body).error).toContain('不会提交真实充值')
  })
})
