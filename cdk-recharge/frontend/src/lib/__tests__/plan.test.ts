import { describe, expect, it } from 'vitest'

import { isCardAttachPlan, planLabel, planSatisfied } from '../plan'

describe('planSatisfied · 绑卡档（Pro 20x 续费）', () => {
  it('账号已是 Pro 20x 时仍必须可买', () => {
    for (const current of ['pro_20x', 'pro', 'chatgptproplan', 'plus', 'free', '']) {
      expect(planSatisfied(current, 'pro_20x_renew')).toBe(false)
    }
  })

  it('Pro 5x 续费可用于已有订阅，显式 flow 仍优先', () => {
    expect(planLabel('pro_5x_renew')).toBe('Pro 5x 续费')
    expect(isCardAttachPlan(' PRO_5X_RENEW ')).toBe(true)
    for (const current of ['pro_5x', 'prolite', 'pro_20x']) {
      expect(planSatisfied(current, 'pro_5x_renew')).toBe(false)
    }
    expect(isCardAttachPlan('pro_5x_renew', 'direct')).toBe(false)
    expect(planSatisfied('pro_5x', 'pro_5x_renew', 'direct')).toBe(true)
  })

  it('后端下发了 plan_flow 时以后端为准', () => {
    expect(planSatisfied('pro_20x', 'pro_20x_renew', 'card_attach')).toBe(false)
    expect(isCardAttachPlan('unknown_key', 'card_attach')).toBe(true)
  })

  it('普通订阅档的判据不受影响', () => {
    expect(planSatisfied('pro_20x', 'pro_20x')).toBe(true)
    expect(planSatisfied('plus', 'pro_20x')).toBe(false)
    expect(planSatisfied('plus', 'pro_5x')).toBe(false)
    expect(planSatisfied('pro_20x', 'plus')).toBe(true)
    expect(planSatisfied('free', 'plus')).toBe(false)
  })

  it('点数档永远不判已满足', () => {
    expect(planSatisfied('pro_20x', 'credit250')).toBe(false)
  })
})

describe('planLabel', () => {
  it('50x is distinct from 20x and allows upgrades from existing lower subscriptions', () => {
    for (const current of ['plus', 'prolite', 'pro', 'pro_20x', 'chatgptpro']) {
      expect(planSatisfied(current, 'pro_50x')).toBe(false)
    }
    for (const current of ['pro_50x', 'promax', 'chatgptpromaxplan']) {
      expect(planLabel(current)).toBe('Pro 50x')
      expect(planSatisfied(current, 'pro_50x')).toBe(true)
      expect(planSatisfied(current, 'pro_20x')).toBe(true)
      expect(planSatisfied(current, 'credit25000')).toBe(false)
    }
  })

  it('续费档显示为 Pro 20x 续费', () => {
    expect(planLabel('pro_20x_renew')).toBe('Pro 20x 续费')
  })

  it('保留既有档位文案', () => {
    expect(planLabel('pro_20x')).toBe('Pro 20x')
    expect(planLabel('pro')).toBe('Pro 20x')
    expect(planLabel('pro_5x')).toBe('Pro 5x')
    expect(planLabel('chatgptprolite')).toBe('Pro 5x')
    expect(planLabel('plus')).toBe('Plus')
    expect(planLabel('free')).toBe('免费版')
  })
})
