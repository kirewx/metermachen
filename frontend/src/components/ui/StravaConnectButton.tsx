import { useState } from 'react'

/**
 * Offizieller „Connect with Strava"-Button gemäß Strava-Brand-Guidelines.
 * Marken-Asset (orange) unter public/strava/ — siehe public/strava/README.md.
 * Fehlt die Datei, greift ein orangefarbener Text-Fallback.
 *
 * Verlinkt auf /api/strava/connect → Redirect zu strava.com/oauth/authorize.
 */
export default function StravaConnectButton() {
  const [assetFehlt, setAssetFehlt] = useState(false)
  return (
    <a
      href="/api/strava/connect"
      aria-label="Connect with Strava"
      className="inline-flex items-center"
    >
      {assetFehlt ? (
        <span
          className="inline-flex h-12 items-center rounded-md px-4 text-sm font-bold text-white"
          style={{ backgroundColor: '#FC5200' }}
        >
          Connect with Strava
        </span>
      ) : (
        <img
          src="/strava/connect-with-strava-orange.png"
          srcSet="/strava/connect-with-strava-orange.png 1x, /strava/connect-with-strava-orange@2x.png 2x"
          alt="Connect with Strava"
          width={237}
          height={48}
          className="h-12 w-auto"
          onError={() => setAssetFehlt(true)}
        />
      )}
    </a>
  )
}
