export type PaymentRegion = { country: string; currency: string }

export function paymentRegionsFromResponse(value: unknown): PaymentRegion[] {
  if (!Array.isArray(value)) return []
  return value.map((item: any) => ({
    country: String(item?.country || ''),
    currency: String(item?.currency || ''),
  })).filter((region) => region.country && region.currency)
}

export function availablePaymentCountry(selected: string, regions: PaymentRegion[]): string {
  return selected && regions.some((region) => region.country === selected) ? selected : ''
}
