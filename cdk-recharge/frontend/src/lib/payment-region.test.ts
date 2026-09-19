import { describe, expect, it } from 'vitest'
import { availablePaymentCountry, paymentRegionsFromResponse } from './payment-region'

describe('payment region selection', () => {
  it('uses only the regions and currencies returned by the card platform', () => {
    expect(paymentRegionsFromResponse([
      { country: 'CL', currency: 'CLP' },
      { country: 'JP', currency: 'JPY' },
      { country: '', currency: 'USD' },
    ])).toEqual([
      { country: 'CL', currency: 'CLP' },
      { country: 'JP', currency: 'JPY' },
    ])
  })

  it('falls back to the default region when the platform does not provide a list', () => {
    expect(paymentRegionsFromResponse(undefined)).toEqual([])
    expect(paymentRegionsFromResponse({ country: 'CL' })).toEqual([])
    expect(availablePaymentCountry('CL', [])).toBe('')
  })

  it('keeps a supported selection and discards one removed by the platform', () => {
    const regions = [{ country: 'JP', currency: 'JPY' }]
    expect(availablePaymentCountry('JP', regions)).toBe('JP')
    expect(availablePaymentCountry('CL', regions)).toBe('')
    expect(availablePaymentCountry('', regions)).toBe('')
  })
})
