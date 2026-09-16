import { describe, expect, it, vi } from 'vitest'
import { createSetupStatusCache } from './setup-status'

describe('setup status cache', () => {
  it('treats a completed bootstrap as installed without redirecting back to setup', async () => {
    const fetchStatus = vi.fn(async () => false)
    const cache = createSetupStatusCache(fetchStatus)

    expect(await cache.ensure()).toBe(false)
    cache.markInstalled()

    expect(await cache.ensure()).toBe(true)
    expect(fetchStatus).toHaveBeenCalledTimes(1)
  })
})
