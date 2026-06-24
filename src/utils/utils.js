/**
 * Utils: Utilities.
 * - Global functions that can be used across multiple files.
 * -----------------------------------------------------------------------------
 */

/**
 * Config object.
 */
const config = {
  authNamespace: 'nowify_auth_state'
}

/**
 * Get stored authorisation object.
 * @return {Object}
 */
export function getStoredAuth() {
  return JSON.parse(window.localStorage.getItem(config.authNamespace)) || {}
}

/**
 * Set stored authorisation object.
 * @return {Object}
 */
export function setStoredAuth(authState = {}) {
  window.localStorage.setItem(config.authNamespace, JSON.stringify(authState))
}

/**
 * PKCE: key used to persist the code verifier across the Spotify redirect.
 */
const codeVerifierKey = 'nowify_code_verifier'

/**
 * Generate a high-entropy PKCE code verifier (43-128 chars).
 * @param {Number} length
 * @return {String}
 */
export function generateCodeVerifier(length = 64) {
  const possible =
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  const values = crypto.getRandomValues(new Uint8Array(length))
  return values.reduce((acc, x) => acc + possible[x % possible.length], '')
}

/**
 * Derive the S256 code challenge (base64url SHA-256) from a verifier.
 * @param {String} verifier
 * @return {Promise<String>}
 */
export async function generateCodeChallenge(verifier) {
  const data = new TextEncoder().encode(verifier)
  const digest = await window.crypto.subtle.digest('SHA-256', data)
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
}

/**
 * Persist / retrieve the code verifier between authorize and token exchange.
 */
export function setCodeVerifier(verifier) {
  window.localStorage.setItem(codeVerifierKey, verifier)
}

export function getCodeVerifier() {
  return window.localStorage.getItem(codeVerifierKey)
}
