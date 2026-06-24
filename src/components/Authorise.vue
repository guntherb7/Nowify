<template>
  <div class="authorise">
    <h1 class="authorise__heading">Nowify</h1>

    <p class="authorise__copy">
      Nowify is a simple Spotify 'Now Playing' screen designed for the Raspberry
      Pi. Login with Spotify below and start playing some music!
    </p>

    <button
      class="authorise__button button button--authorise"
      @click="initAuthorise"
    >
      Login with Spotify
    </button>

    <p class="authorise__credit">
      <a href="https://github.com/jonashcroft/Nowify">View on GitHub</a>
    </p>
  </div>
</template>

<script>
import props from '@/utils/props.js'
import {
  setStoredAuth,
  generateCodeVerifier,
  generateCodeChallenge,
  setCodeVerifier,
  getCodeVerifier
} from '@/utils/utils.js'

const searchParams = new URLSearchParams()
const currentParams = new URLSearchParams(window.location.search)

export default {
  name: 'Authorise',

  components: {},

  props: {
    auth: props.auth,
    endpoints: props.endpoints
  },

  data() {
    return {}
  },

  computed: {},

  mounted() {
    /**
     * Set access token on load.
     */
    this.getUrlAuthCode()

    /**
     * Refresh token already exists - we must get a new one.
     */
    if (this.auth.refreshToken) {
      this.requestAccessTokens('refresh_token')
    }
  },

  methods: {
    /**
     * Initial Spotify auth, redirects the user to
     * Spotify to grant app consent, user will
     * be redirected back to the app.
     */
    async initAuthorise() {
      await this.setAuthUrl()
      window.location.href = `${this.endpoints.auth}?${searchParams.toString()}`
    },

    /**
     * Check to see if the URL contains an auth code
     * returned after the user grants consent from Spotify.
     */
    getUrlAuthCode() {
      const urlAuthCode = currentParams.get('code')

      if (!urlAuthCode) {
        return
      }

      this.auth.authCode = urlAuthCode
    },

    /**
     * Request the initial access and refresh tokens from Spotify.
     */
    async requestAccessTokens(grantType = 'authorization_code') {
      // PKCE flow: the client_id is sent in the body and no client secret is
      // used. authorization_code also sends the stored code_verifier.
      let fetchData = {
        grant_type: grantType,
        client_id: this.auth.clientId
      }

      if (grantType === 'authorization_code') {
        fetchData.code = this.auth.authCode
        fetchData.redirect_uri = window.location.origin
        fetchData.code_verifier = getCodeVerifier()
      }

      if (grantType === 'refresh_token') {
        fetchData.refresh_token = this.auth.refreshToken
      }

      const res = await fetch(`${this.endpoints.token}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: new URLSearchParams(fetchData).toString()
      })

      const data = await res.json()

      this.handleAccessTokenResponse(data)
    },

    /**
     * Handle the data returned from Spotify.
     * @param {Object} accessTokenResponse - response object from fetch.
     */
    handleAccessTokenResponse(accessTokenResponse = {}) {
      /**
       * Refresh token is expired, revoked, or otherwise invalid. The Spotify
       * token endpoint returns a flat `{ error: 'invalid_grant' }` (a string,
       * not an object). Discard the stored tokens and fall back to the login
       * screen instead of retrying — a refresh can never recover from this, so
       * the user must sign in again (Spotify's 6-month refresh-token policy).
       */
      if (accessTokenResponse.error === 'invalid_grant') {
        this.auth.accessToken = ''
        this.auth.refreshToken = ''
        this.auth.authCode = ''
        this.auth.status = false
        setStoredAuth(this.auth)

        return
      }

      /**
       * Access Token has expired.
       */
      if (accessTokenResponse.error?.status === 401) {
        this.auth.authCode = ''
        this.auth.status = false

        return
      }

      /**
       * Successful.
       */
      if (accessTokenResponse.access_token) {
        this.auth.accessToken = accessTokenResponse.access_token

        if (accessTokenResponse.refresh_token) {
          this.auth.refreshToken = accessTokenResponse.refresh_token
        }

        this.auth.status = true

        /**
         * There has to be a better way than this.
         */
        const param = param != 'undefined' ? param : ''
        window.history.replaceState(
          null,
          null,
          location.protocol +
            '//' +
            location.host +
            location.pathname +
            location.search
              .replace(/[?&]code=[^&]+/, '')
              .replace(/^&/, '?')
              .replace(/[?&]state=[^&]+/, '')
              .replace(/^&/, '?')
        )
      }
    },

    /**
     * Set the initial Spotify authorisation URL
     * in which the user will be redirected to.
     */
    async setAuthUrl() {
      // PKCE: create a verifier, persist it for the token exchange, and send
      // its S256 challenge on the authorize request.
      const codeVerifier = generateCodeVerifier(64)
      setCodeVerifier(codeVerifier)
      const codeChallenge = await generateCodeChallenge(codeVerifier)

      searchParams.append('client_id', this.auth.clientId)
      searchParams.append('response_type', 'code')
      searchParams.append('redirect_uri', window.location.origin)
      searchParams.append('code_challenge_method', 'S256')
      searchParams.append('code_challenge', codeChallenge)
      searchParams.append(
        'state',
        [
          Math.random()
            .toString(33)
            .substring(2),
          Math.random()
            .toString(34)
            .substring(3),
          Math.random()
            .toString(35)
            .substring(4),
          Math.random()
            .toString(36)
            .substring(5)
        ].join('-')
      )
      searchParams.append('scope', 'user-read-currently-playing')

      return `${this.endpoints.auth}?${searchParams.toString()}`
    }
  },

  watch: {
    /**
     * Watch authorisation code.
     */
    'auth.authCode': function() {
      this.requestAccessTokens()
    },

    /**
     * Watch authorisation status.
     */
    'auth.status': function() {
      if (this.auth.refreshToken) {
        this.requestAccessTokens('refresh_token')
      }
    }
  }
}
</script>

<style src="@/styles/components/authorise.scss" lang="scss" scoped></style>
