export type SetupStatusFetcher = () => Promise<boolean>

export function createSetupStatusCache(fetchStatus: SetupStatusFetcher) {
  let checked = false
  let installed = true

  return {
    async ensure(): Promise<boolean> {
      if (checked) return installed
      try {
        installed = await fetchStatus()
      } catch {
        installed = true
      }
      checked = true
      return installed
    },
    markInstalled() {
      installed = true
      checked = true
    },
  }
}
