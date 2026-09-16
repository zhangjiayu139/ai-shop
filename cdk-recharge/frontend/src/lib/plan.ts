// 套餐判定：可读名 + 「账号是否已满足该档」（兑换前的重复购买闸）。

/** 绑卡档 flow：本单不扣款，只把新卡绑上并设为默认（Pro 20x 续费）。 */
export const FLOW_CARD_ATTACH = 'card_attach'

/** 优先信任卡台预览下发的 plan_flow，缺失时才按已知键名兜底。 */
export function isCardAttachPlan(plan: string, planFlow?: string): boolean {
  const flow = String(planFlow || '').trim().toLowerCase()
  if (flow) return flow === FLOW_CARD_ATTACH
  return String(plan || '').trim().toLowerCase() === 'pro_20x_renew'
}

export function planLabel(value: string): string {
  const n = String(value || 'free').trim().toLowerCase()
  if (n === 'pro_20x_renew' || n.includes('renew')) return 'Pro 20x 续费'
  if (n.includes('prolite') || n.includes('5x') || n === 'pro_5x') return 'Pro 5x'
  if (n.includes('20x') || n === 'pro_20x' || n === 'pro' || n === 'chatgptpro' || n.includes('pro')) return 'Pro 20x'
  if (n.includes('plus')) return 'Plus'
  if (n.includes('team')) return 'Team'
  if (!n || n === 'free') return '免费版'
  return value
}

/** 绑卡/点数档不能用当前订阅等级判「已满足」。 */
export function planSatisfied(currentPlan: string, requestedPlan: string, planFlow?: string): boolean {
  const current = String(currentPlan || '').trim().toLowerCase()
  const req = String(requestedPlan || '').trim().toLowerCase()
  if (isCardAttachPlan(req, planFlow)) return false
  const currentRank =
    current.includes('prolite') || current.includes('5x') || current === 'pro_5x'
      ? 2
      : current.includes('pro')
        ? 3
        : current.includes('plus')
          ? 1
          : 0
  const requestedRank =
    req === 'pro_20x' || req === 'pro' || req.includes('20x')
      ? 3
      : req === 'pro_5x' || req.includes('5x')
        ? 2
        : req === 'plus' || req.includes('plus')
          ? 1
          : 99
  return currentRank >= requestedRank
}
