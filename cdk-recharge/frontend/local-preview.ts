import type { IncomingMessage, ServerResponse } from 'node:http'

/** Preview-only middleware: never forward a business request to a real backend. */
export function localPreviewApi(req: IncomingMessage, res: ServerResponse, next: () => void) {
  if (!req.url?.startsWith('/api/')) return next()
  const path = new URL(req.url, 'http://localhost').pathname
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.setHeader('Cache-Control', 'no-store')
  if (path === '/api/v1/public/site') {
    res.end(JSON.stringify({ brand_name: 'TaoAi CDK自助充值', theme_mode: 'light', skin: 'terracotta' }))
  } else if (path === '/api/v1/setup/status') {
    res.end(JSON.stringify({ installed: true }))
  } else {
    res.statusCode = 503
    res.end(JSON.stringify({ error: '当前为本地界面预览，不会提交真实充值，也不会查询真实账号。' }))
  }
}
