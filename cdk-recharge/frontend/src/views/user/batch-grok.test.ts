// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import BatchRedeemView from './BatchRedeemView.vue'
import { i18n, setLocale } from '../../i18n'
import * as XLSX from 'xlsx'

let wrapper: VueWrapper | undefined
const raw = 'sso=' + 'synthetic-grok-cookie'.repeat(3)
const reply = (data: unknown) => new Response(JSON.stringify(data))
beforeEach(() => { localStorage.clear(); sessionStorage.clear(); setLocale('zh') })
afterEach(() => { wrapper?.unmount(); wrapper = undefined; vi.unstubAllGlobals() })

it('keeps three Excel accounts paired with their original CDKs during automatic submission', async () => {
  const cookies = ['a', 'b', 'c'].map(c => 'lang=en; tracking=' + 'x'.repeat(90) + '; sso=' + c.repeat(32))
  const pairs: Record<string, string> = {}
  vi.stubGlobal('fetch', vi.fn(async (path: string, init: RequestInit) => {
    const body = JSON.parse(init.body as string)
    if (path.endsWith('/preview')) return reply({ redemption_token: body.code, plan: 'monthly' })
    if (path.endsWith('/preflight')) return reply({ code: 0, data: { currentPlan: 'free' } })
    if (path.endsWith('/redeem')) {
      pairs[body.redemption_token] = body.credential.session
      return reply({ order: { status: 'completed' } })
    }
    throw new Error(`Unexpected test endpoint: ${path}`)
  }))
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: BatchRedeemView }] })
  await router.push('/batch'); await router.isReady()
  wrapper = mount(BatchRedeemView, { global: { plugins: [router, i18n], stubs: { LanguageToggle: true, ThemeToggle: true, ExcelImportBlock: true } } })
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([['session'], ...cookies.map(c => [c])]), 'accounts')
  wrapper.findComponent({ name: 'ExcelImportBlock' }).vm.$emit('pick', {
    name: 'synthetic-accounts.xlsx', arrayBuffer: async () => XLSX.write(wb, { type: 'array', bookType: 'xlsx' }),
  })
  await flushPromises()
  await vi.waitFor(() => expect(wrapper!.findComponent({ name: 'ExcelImportBlock' }).props('importing')).toBe(false))
  await wrapper.get('textarea').setValue('CDK-ACCOUNT-A\nCDK-ACCOUNT-B\nCDK-ACCOUNT-C')
  await wrapper.get('button.btn-primary').trigger('click'); await flushPromises()
  const automatic = wrapper.findAll('button').find(b => b.text().includes('自动'))!
  await automatic.trigger('click'); await flushPromises()
  expect(pairs).toEqual({ 'CDK-ACCOUNT-A': cookies[0], 'CDK-ACCOUNT-B': cookies[1], 'CDK-ACCOUNT-C': cookies[2] })
})

it.each([
  { plan: 'monthly', blocking: '', redeemed: true },
  { plan: 'monthly', blocking: '已有订阅，不能开通', redeemed: false },
  { plan: 'plus', blocking: '', redeemed: false },
])('batch $plan blocking=$blocking keeps product-specific redemption gates', async ({ plan, blocking, redeemed }) => {
  const request = vi.fn(async (path: string) => {
    if (path.endsWith('/preview')) return reply({ redemption_token: 'fixture-redemption', plan })
    if (path.endsWith('/preflight')) return reply({ code: 0, data: { blocking_reason: blocking, currentPlan: 'free' } })
    if (path.endsWith('/redeem')) return reply({ order: { status: 'completed' } })
    throw new Error(`Unexpected test endpoint: ${path}`)
  })
  vi.stubGlobal('fetch', request)
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: BatchRedeemView }] })
  await router.push('/batch'); await router.isReady()
  wrapper = mount(BatchRedeemView, { global: { plugins: [router, i18n], stubs: { LanguageToggle: true, ThemeToggle: true, ExcelImportBlock: true } } })
  await wrapper.get('textarea').setValue('TEST-GROK-CDK-CODE')
  await wrapper.get('button.btn-primary').trigger('click'); await flushPromises()
  await wrapper.get('textarea').setValue(raw)
  await wrapper.get('button.btn-primary').trigger('click'); await flushPromises()
  const redeem = request.mock.calls.find(c => c[0].endsWith('/redeem'))
  expect(!!redeem).toBe(redeemed)
  if (redeem) {
    const body = JSON.parse((redeem as unknown as [string, RequestInit])[1].body as string)
    expect(body.credential).toEqual({ mode: 'session', session: raw })
    expect(body).not.toHaveProperty('preflight_token')
  }
  if (blocking) expect(wrapper.text()).toContain(blocking)
  expect(JSON.stringify({ ...localStorage, ...sessionStorage })).not.toContain(raw)
})
