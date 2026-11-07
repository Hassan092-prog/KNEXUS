/** UUID v4 generation that works in Node and browser/jsdom runtimes. */
export function randomUuid(): string {
  const cryptoRef = globalThis.crypto as Crypto | undefined
  if (cryptoRef !== undefined && typeof cryptoRef.randomUUID === "function") {
    return cryptoRef.randomUUID()
  }
  // RFC 4122 v4 fallback (e.g. jsdom lacks Crypto.randomUUID).
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replaceAll(/[xy]/g, (character) => {
    const random = Math.trunc(Math.random() * 16)
    const value = character === "x" ? random : (random & 0x3) | 0x8
    return value.toString(16)
  })
}
