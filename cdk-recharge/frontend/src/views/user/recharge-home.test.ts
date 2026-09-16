// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { nextTick } from 'vue'
import RechargeView from './RechargeView.vue'
import HomeView from '../HomeView.vue'
import { i18n, setLocale } from '../../i18n'

const SESSION = '{"user":{"email":"demo@example.invalid"},"sessionToken":"test-only-session"}'
const preview = { redemption_token: 'test-redemption', plan: 'plus' }
const preflight = { code: 0, data: { preflight_token: 'test-preflight', email: 'demo@example.invalid', currentPlan: 'free', subscription_has_active: false, subscription_is_delinquent: false } }
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
let wrapper: VueWrapper | undefined
let request: ReturnType<typeof vi.fn>

async function open(view = RechargeView, path = '/') {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/', component: HomeView }, { path: '/recharge', component: RechargeView },
    { path: '/batch', component: { template: '<div>batch</div>' } },
    { path: '/history', component: { template: '<div>history</div>' } },
    { path: '/billing', component: { template: '<div>billing</div>' } },
  ] })
  await router.push(path)
  await router.isReady()
  wrapper = mount(view, { global: { plugins: [router, i18n], stubs: { ElTag: { template: '<span><slot /></span>' }, ElIcon: { template: '<span><slot /></span>' }, Tickets: true } } })
  await flushPromises()
  return wrapper
}

async function fill(w: VueWrapper, mode: 'session' | 'mailbox' = 'session') {
  await w.get('input[aria-label="CDK 卡密"]').setValue('DEMO-CDK-001')
  if (mode === 'session') await w.get('textarea').setValue(SESSION)
  else {
    await w.get('[data-testid="mailbox-mode"]').trigger('click')
    await w.get('input[type="email"]').setValue('demo@example.invalid')
    await w.get('input[type="password"]').setValue('test-only-password')
  }
}

async function validate(w: VueWrapper) {
  await w.get('form').trigger('submit')
  await flushPromises()
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  setLocale('zh')
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false, addEventListener() {}, removeEventListener() {} })))
  request = vi.fn(async (path: string) => {
    if (path.endsWith('/preview')) return reply(preview)
    if (path.endsWith('/preflight')) return reply(preflight)
    if (path.endsWith('/redeem')) return reply({ order: { status: 'pending', account_email: 'demo@example.invalid' } }, 202)
    if (path.includes('/result')) return reply({ order: { status: 'completed', account_email: 'demo@example.invalid' }, events: [] })
    throw new Error(`Unexpected test request: ${path}`)
  })
  vi.stubGlobal('fetch', request)
})

afterEach(() => { wrapper?.unmount(); wrapper = undefined; vi.unstubAllGlobals() })

describe('three-step recharge', () => {
  it('shows CDK and Session together with exactly three steps', async () => {
    const w = await open()
    expect(w.get('input[aria-label="CDK 卡密"]').isVisible()).toBe(true)
    expect(w.get('textarea').isVisible()).toBe(true)
    expect(w.findAll('[data-flow-step]')).toHaveLength(3)
    expect(w.text()).toContain('填写信息')
    expect(request).not.toHaveBeenCalled()
  })

  it('makes the real recharge form the homepage and retains three secondary links', async () => {
    const w = await open(HomeView)
    expect(w.find('input[aria-label="CDK 卡密"]').exists()).toBe(true)
    for (const path of ['/batch', '/history', '/billing']) expect(w.find(`a[href="${path}"]`).exists()).toBe(true)
    expect(w.find('.service-list').exists()).toBe(false)
  })

  it('previews then preflights, and does not redeem without confirmation', async () => {
    const w = await open(); await fill(w); await validate(w)
    expect(request.mock.calls.map(c => c[0])).toEqual(['/api/v1/public/cdk/preview', '/api/v1/public/cdk/preflight'])
    expect(w.get('[data-testid="confirm-panel"]').isVisible()).toBe(true)
    expect(w.text()).toContain('demo@example.invalid')
    expect(JSON.parse(request.mock.calls[1][1].body).credential.session).toBe(SESSION)
  })

  it('opens subscription and payment details by default on confirmation', async () => {
    const w = await open(); await fill(w); await validate(w)
    const details = w.get('details.subscription-details')
    expect(details.get('summary').text()).toBe('订阅与付款详情')
    expect((details.element as HTMLDetailsElement).open).toBe(true)
    expect(request.mock.calls.map(c => c[0])).toEqual(['/api/v1/public/cdk/preview', '/api/v1/public/cdk/preflight'])
  })

  it('does not preflight an invalid CDK and keeps the credentials for correction', async () => {
    request.mockResolvedValueOnce(reply({ error: '卡密无效' }, 400))
    const w = await open(); await fill(w); await validate(w)
    expect(request).toHaveBeenCalledTimes(1)
    expect(w.text()).toContain('卡密无效')
    expect(w.get('textarea').element.value).toBe(SESSION)
  })

  it('keeps a valid preview when credentials fail', async () => {
    request.mockResolvedValueOnce(reply(preview)).mockResolvedValueOnce(reply({ error: '凭证已过期' }, 400))
    const w = await open(); await fill(w); await validate(w)
    expect(w.get('form').isVisible()).toBe(true)
    expect(w.text()).toContain('凭证已过期')
    expect(w.text()).toContain('Plus')
  })

  it('handles network errors and releases the busy lock', async () => {
    request.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    const w = await open(); await fill(w); await validate(w)
    expect(w.text()).toContain('网络')
    expect(w.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
  })

  it('supports the mailbox credential mode', async () => {
    const w = await open(); await fill(w, 'mailbox'); await validate(w)
    expect(JSON.parse(request.mock.calls[1][1].body).credential).toEqual({ mode: 'mailbox', email: 'demo@example.invalid', password: 'test-only-password' })
    expect(w.get('[data-testid="confirm-panel"]').isVisible()).toBe(true)
  })

  it('guards duplicate validation clicks while preview is pending', async () => {
    let finish!: (r: Response) => void
    request.mockReturnValueOnce(new Promise<Response>(resolve => { finish = resolve }))
    const w = await open(); await fill(w)
    await w.get('form').trigger('submit'); await w.get('form').trigger('submit')
    expect(request).toHaveBeenCalledTimes(1)
    finish(reply(preview)); await flushPromises()
    expect(request).toHaveBeenCalledTimes(2)
  })

  it('clears only credentials without losing the CDK', async () => {
    const w = await open(); await fill(w)
    await w.get('[data-testid="clear-credentials"]').trigger('click')
    expect(w.get('textarea').element.value).toBe('')
    expect(w.get('input[aria-label="CDK 卡密"]').element.value).toBe('DEMO-CDK-001')
  })

  it('submits only on confirmation and clears sensitive inputs for the next card', async () => {
    const w = await open(); await fill(w); await validate(w)
    await w.get('[data-testid="confirm-redeem"]').trigger('click'); await flushPromises()
    expect(request.mock.calls.filter(c => c[0].endsWith('/redeem'))).toHaveLength(1)
    expect(w.get('[data-testid="result-panel"]').isVisible()).toBe(true)
    await w.get('[data-testid="reset-recharge"]').trigger('click'); await nextTick()
    expect(w.get('textarea').element.value).toBe('')
    expect(w.get('input[aria-label="CDK 卡密"]').element.value).toBe('')
  })

  it('restores the existing four-step result record to the third screen', async () => {
    sessionStorage.setItem('cdk_redeem_progress_v1', JSON.stringify({ step: 4, code: 'DEMO-CDK-001', redemptionToken: 'test-redemption', savedAt: Date.now() }))
    const w = await open()
    expect(w.get('[data-testid="result-panel"]').isVisible()).toBe(true)
    expect(w.get('[data-flow-step="3"]').attributes('aria-current')).toBe('step')
  })

  it('preserves a code provided through the legacy recharge URL', async () => {
    const w = await open(RechargeView, '/recharge?cdk=DEMO-URL-CDK')
    expect(w.get('input[aria-label="CDK 卡密"]').element.value).toBe('DEMO-URL-CDK')
  })

  it('translates the new form when language switches', async () => {
    const w = await open()
    setLocale('en'); await nextTick()
    expect(w.text()).toContain('Verify and continue')
    expect(w.text()).toContain('Account credentials')
  })

  it('invalidates the old account summary after editing credentials', async () => {
    const w = await open(); await fill(w); await validate(w)
    await w.get('[data-testid="edit-details"]').trigger('click')
    await w.get('textarea').setValue('{"sessionToken":"different-test-session"}')
    expect(w.text()).not.toContain('demo@example.invalid')
    const saved = JSON.parse(sessionStorage.getItem('cdk_redeem_progress_v1') || '{}')
    expect(saved.preflightToken).toBe('')
    expect(saved.account.checked).toBe(false)
    expect(saved).not.toHaveProperty('sessionRaw')
  })

  it('ignores a preflight response after the input changes', async () => {
    let finish!: (r: Response) => void
    request.mockResolvedValueOnce(reply(preview)).mockReturnValueOnce(new Promise<Response>(resolve => { finish = resolve }))
    const w = await open(); await fill(w); await validate(w)
    // Test Utils deliberately suppresses trigger() on disabled controls. Dispatch the
    // programmatic input event directly to exercise stale-response protection too.
    const textarea = w.get('textarea').element
    textarea.value = '{"sessionToken":"changed-test-session"}'
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick()
    finish(reply(preflight)); await flushPromises()
    expect(w.get('form').isVisible()).toBe(true)
    expect(w.get('[data-testid="confirm-panel"]').isVisible()).toBe(false)
  })

  it('preserves already-satisfied plan blocking and the delinquency warning', async () => {
    request.mockResolvedValueOnce(reply(preview)).mockResolvedValueOnce(reply({ code: 0, data: { ...preflight.data, currentPlan: 'plus', subscription_has_active: true, subscription_is_delinquent: true } }))
    const w = await open(); await fill(w); await validate(w)
    expect(w.get('[data-testid="confirm-redeem"]').attributes('disabled')).toBeDefined()
    expect(w.text()).toContain('未结清账单')
  })

  it('keeps Pro 20x renewal redeemable for an existing Pro 20x account', async () => {
    request
      .mockResolvedValueOnce(reply({ ...preview, plan: 'pro_20x_renew', plan_flow: 'card_attach' }))
      .mockResolvedValueOnce(reply({
        code: 0,
        data: {
          ...preflight.data,
          currentPlan: 'pro_20x',
          subscription_has_active: true,
        },
      }))
    const w = await open(); await fill(w); await validate(w)
    expect(w.text()).toContain('Pro 20x 续费')
    expect(w.get('[data-testid="confirm-redeem"]').attributes('disabled')).toBeUndefined()
  })

  it('does not invent a free plan or verified account when the summary is absent', async () => {
    request.mockResolvedValueOnce(reply(preview)).mockResolvedValueOnce(reply({ code: 0, data: { preflight_token: 'test-preflight' } }))
    const w = await open(); await fill(w); await validate(w)
    const confirmation = w.get('[data-testid="confirm-panel"]')
    expect(confirmation.text()).not.toContain('免费版')
    expect(confirmation.text()).not.toContain('账号已验证')
    expect(confirmation.text()).toContain('预检未返回账号摘要')
    expect(w.get('[data-testid="confirm-redeem"]').attributes('disabled')).toBeUndefined()
  })

  it('restores delinquency facts from an existing confirmation checkpoint', async () => {
    sessionStorage.setItem('cdk_redeem_progress_v1', JSON.stringify({ step: 3, code: 'DEMO-CDK-001', redemptionToken: 'test-redemption', preflightToken: 'test-preflight', account: { checked: true, email: 'demo@example.invalid', subscriptionIsDelinquent: true }, savedAt: Date.now() }))
    const w = await open()
    expect(w.get('[data-testid="confirm-panel"]').isVisible()).toBe(true)
    expect(w.text()).toContain('未结清账单')
  })

  it('recovers a previously used CDK without submitting another redemption', async () => {
    request.mockResolvedValueOnce(reply({ error: '卡密已使用' }, 400))
    const w = await open(); await fill(w); await validate(w)
    expect(w.get('[data-testid="result-panel"]').isVisible()).toBe(true)
    expect(request.mock.calls.some(c => c[0].includes('/result-by-code'))).toBe(true)
    expect(request.mock.calls.some(c => c[0].endsWith('/redeem'))).toBe(false)
  })

  it('does not label review as success or allow starting another redemption', async () => {
    request.mockImplementation(async (path: string) => {
      if (path.endsWith('/preview')) return reply(preview)
      if (path.endsWith('/preflight')) return reply(preflight)
      return reply({ order: { status: 'review' }, events: [] })
    })
    const w = await open(); await fill(w); await validate(w)
    await w.get('[data-testid="confirm-redeem"]').trigger('click'); await flushPromises()
    expect(w.get('[data-testid="result-panel"]').text()).not.toContain('开通完成')
    expect(w.get('[data-testid="reset-recharge"]').attributes('disabled')).toBeDefined()
  })

  it('checkpoints uncertain submission outcomes on the result screen', async () => {
    request.mockImplementation(async (path: string) => {
      if (path.endsWith('/preview')) return reply(preview)
      if (path.endsWith('/preflight')) return reply(preflight)
      if (path.endsWith('/redeem')) throw new TypeError('connection interrupted')
      return reply({ order: { status: 'pending' }, events: [] })
    })
    const w = await open(); await fill(w); await validate(w)
    await w.get('[data-testid="confirm-redeem"]').trigger('click'); await flushPromises()
    expect(w.get('[data-testid="result-panel"]').isVisible()).toBe(true)
    const saved = JSON.parse(sessionStorage.getItem('cdk_redeem_progress_v1') || '{}')
    expect(saved.step).toBe(4)
    expect(w.get('[data-testid="reset-recharge"]').attributes('disabled')).toBeDefined()
    expect(request.mock.calls.filter(c => c[0].endsWith('/redeem'))).toHaveLength(1)
  })

  it('returns a definite validation rejection without an order to revalidation', async () => {
    request.mockImplementation(async (path: string) => {
      if (path.endsWith('/preview')) return reply(preview)
      if (path.endsWith('/preflight')) return reply(preflight)
      if (path.endsWith('/redeem')) return reply({ error: '预检已过期，请重新校验' }, 400)
      return reply({ error: '兑换结果不存在' }, 404)
    })
    const w = await open(); await fill(w); await validate(w)
    await w.get('[data-testid="confirm-redeem"]').trigger('click'); await flushPromises()
    expect(w.get('form').isVisible()).toBe(true)
    expect(w.text()).toContain('预检已过期')
    expect(w.get('input[aria-label="CDK 卡密"]').element.value).toBe('DEMO-CDK-001')
    const saved = JSON.parse(sessionStorage.getItem('cdk_redeem_progress_v1') || '{}')
    expect(saved.step).toBe(1)
    expect(saved.preflightToken).toBe('')
    expect(request.mock.calls.some(c => c[0].includes('/result'))).toBe(false)
  })

  it.each([
    [401, { error: '认证失败，请重新校验' }],
    [403, { error: '权限未开启，请重新校验' }],
    [401, { code: 401, msg: '认证失败，请重新校验' }],
    [403, { code: 403, error_code: 'GPT_DIRECT_ACCESS_DENIED', msg: '权限未开启，请重新校验' }],
  ])('returns a definite HTTP %s authentication rejection to revalidation', async (status, body) => {
    request.mockImplementation(async (path: string) => {
      if (path.endsWith('/preview')) return reply(preview)
      if (path.endsWith('/preflight')) return reply(preflight)
      if (path.endsWith('/redeem')) return reply(body, status as number)
      return reply({ error: '兑换结果不存在' }, 404)
    })
    const w = await open(); await fill(w); await validate(w)
    await w.get('[data-testid="confirm-redeem"]').trigger('click'); await flushPromises()
    expect(w.get('form').isVisible()).toBe(true)
    expect(w.text()).toContain('请重新校验')
    expect(w.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
    const saved = JSON.parse(sessionStorage.getItem('cdk_redeem_progress_v1') || '{}')
    expect(saved.step).toBe(1)
    expect(saved.preflightToken).toBe('')
    expect(saved.account.checked).toBe(false)
    expect(request.mock.calls.some(c => c[0].includes('/result'))).toBe(false)
    await validate(w)
    expect(w.get('[data-testid="confirm-panel"]').isVisible()).toBe(true)
    expect(request.mock.calls.filter(c => c[0].endsWith('/redeem'))).toHaveLength(1)
  })

  it.each([401, 403])('does not treat an HTTP %s response carrying a bare order id as unaccepted', async status => {
    request.mockImplementation(async (path: string) => {
      if (path.endsWith('/preview')) return reply(preview)
      if (path.endsWith('/preflight')) return reply(preflight)
      if (path.endsWith('/redeem')) return reply({ code: status, msg: '待确认', data: { id: 981 } }, status)
      return reply({ error: '兑换结果不存在' }, 404)
    })
    const w = await open(); await fill(w); await validate(w)
    await w.get('[data-testid="confirm-redeem"]').trigger('click'); await flushPromises()
    expect(w.get('[data-testid="result-panel"]').isVisible()).toBe(true)
    expect(w.get('[data-testid="reset-recharge"]').attributes('disabled')).toBeDefined()
  })

  it.each([409, 502])('does not retry an uncertain HTTP %s response without an order', async status => {
    request.mockImplementation(async (path: string) => {
      if (path.endsWith('/preview')) return reply(preview)
      if (path.endsWith('/preflight')) return reply(preflight)
      if (path.endsWith('/redeem')) return reply({ error: '待确认' }, status)
      return reply({ error: '兑换结果不存在' }, 404)
    })
    const w = await open(); await fill(w); await validate(w)
    await w.get('[data-testid="confirm-redeem"]').trigger('click'); await flushPromises()
    expect(w.get('[data-testid="result-panel"]').isVisible()).toBe(true)
    expect(w.get('[data-testid="reset-recharge"]').attributes('disabled')).toBeDefined()
  })

  it.each([400, 401, 403, 502])('keeps an uncertain HTTP %s response with an order in the result flow', async status => {
    request.mockImplementation(async (path: string) => {
      if (path.endsWith('/preview')) return reply(preview)
      if (path.endsWith('/preflight')) return reply(preflight)
      if (path.endsWith('/redeem')) return reply({ error: '暂未确认', order: { status: 'pending' } }, status)
      return reply({ error: '兑换结果不存在' }, 404)
    })
    const w = await open(); await fill(w); await validate(w)
    await w.get('[data-testid="confirm-redeem"]').trigger('click'); await flushPromises()
    expect(w.get('[data-testid="result-panel"]').isVisible()).toBe(true)
    expect(w.get('[data-testid="reset-recharge"]').attributes('disabled')).toBeDefined()
  })

  it('ignores a late poll response after resetting for another card', async () => {
    let finish!: (r: Response) => void
    request.mockImplementation(async (path: string) => {
      if (path.endsWith('/preview')) return reply(preview)
      if (path.endsWith('/preflight')) return reply(preflight)
      if (path.endsWith('/redeem')) return reply({ order: { status: 'completed' } })
      return new Promise<Response>(resolve => { finish = resolve })
    })
    const w = await open(); await fill(w); await validate(w)
    await w.get('[data-testid="confirm-redeem"]').trigger('click'); await flushPromises()
    await w.get('[data-testid="reset-recharge"]').trigger('click')
    finish(reply({ order: { status: 'review', account_email: 'old@example.invalid' } })); await flushPromises()
    expect(w.get('form').isVisible()).toBe(true)
    expect(w.text()).not.toContain('old@example.invalid')
  })
})
