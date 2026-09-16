import { describe, expect, it } from 'vitest'
import { restoreRechargeStep, serializeRechargeStep } from './recharge-progress'

describe('backward-compatible recharge progress', () => {
  it.each([[1, 1], [2, 3], [3, 4]])('serializes screen %s using the existing storage contract', (screen, saved) => {
    expect(serializeRechargeStep(screen)).toBe(saved)
  })
  it.each([
    [{ step: 1 }, 1], [{ step: 2 }, 1], [{ step: 3 }, 1], [{ step: 4 }, 1],
    [{ step: 3, preflightToken: 'test-preflight' }, 2],
    [{ step: 4, redemptionToken: 'test-redemption' }, 3],
  ])('restores %j as screen %s', (saved, screen) => {
    expect(restoreRechargeStep(saved)).toBe(screen)
  })
})
