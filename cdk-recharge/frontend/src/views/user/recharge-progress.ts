// Keep the persisted 1/2/3/4 contract so existing sessions can resume safely.
export function serializeRechargeStep(step: number): number {
  return step === 1 ? 1 : step + 1
}

export function restoreRechargeStep(saved: { step?: unknown; redemptionToken?: unknown; preflightToken?: unknown }): 1 | 2 | 3 {
  const step = Number(saved.step)
  if (step >= 4 && saved.redemptionToken) return 3
  if (step === 3 && saved.preflightToken) return 2
  return 1
}
