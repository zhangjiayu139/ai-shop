import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { test } from 'node:test'

// Exercise the actual reset handler without mounting the payment page or calling upstream APIs.
const source = readFileSync(new URL('./RechargeView.vue', import.meta.url), 'utf8')
const handler = source.match(/^function resetAll\(\) \{[\s\S]*?^\}/m)?.[0]
assert.ok(handler, 'RechargeView must expose its resetAll handler')
assert.match(source, /@click="resetAll">再兑一张/)

function resetPreviousRedemption(mode) {
  const state = Object.fromEntries([
    'step', 'busy', 'error', 'code', 'previewInfo', 'redemptionToken', 'preflightToken',
    'sessionRaw', 'email', 'password', 'resultBody', 'resultStatus', 'resultStage',
    'resultMessage', 'resultEmail', 'resultCardLastFour', 'timeline', 'polling',
  ].map(key => [key, { value: 'previous-redemption' }]))
  state.credMode = { value: mode }
  state.sessionRaw.value = '{"sessionToken":"test-only-placeholder"}'
  state.email.value = 'test@example.invalid'
  state.password.value = 'test-only-password'
  let clearedProgress = false
  let clearedAccount = false
  let stoppedPolling = false
  runInNewContext(`${handler}\nresetAll()`, {
    ...state,
    flowVersion: 0,
    pollVersion: 0,
    pollTimer: 123,
    clearInterval: () => { stoppedPolling = true },
    clearProgress: () => { clearedProgress = true },
    clearAccount: () => { clearedAccount = true },
  })
  return { state, clearedProgress, clearedAccount, stoppedPolling }
}

for (const mode of ['session', 'mailbox']) {
  test(`再兑一张 clears all credentials in ${mode} mode`, () => {
    const { state } = resetPreviousRedemption(mode)
    for (const field of ['sessionRaw', 'email', 'password']) {
      assert.equal(state[field].value, '', `${field} must not carry into the next redemption`)
    }
    assert.equal(state.credMode.value, mode, 'preserve the selected credential mode')
  })
}

test('再兑一张 still resets the previous redemption and polling', () => {
  const { state, clearedProgress, clearedAccount, stoppedPolling } = resetPreviousRedemption('session')
  assert.equal(state.step.value, 1)
  for (const key of ['code', 'redemptionToken', 'preflightToken', 'resultEmail', 'resultStatus']) {
    assert.equal(state[key].value, '')
  }
  assert.equal(state.polling.value, false)
  assert.equal(clearedProgress, true)
  assert.equal(clearedAccount, true)
  assert.equal(stoppedPolling, true)
})
