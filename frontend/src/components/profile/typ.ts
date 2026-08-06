import type { ComparisonUser } from '../../api/client'
import { kernSummen, type Achse } from './achsen'

/** Sportler-Typ, abgeleitet aus der eigenen Verteilung — nicht aus dem Rang. */
export type Typ = { key: string; emoji: string; label: string; satz: string }

/** Ab hier lohnt sich eine Aussage über den Typ überhaupt. */
export const MIN_MM = 20
/** Anteil, ab dem eine Disziplin den Typ allein bestimmt. */
export const SCHWELLE_REIN = 0.45
/** Anteil, ab dem zwei Disziplinen gemeinsam den Typ bestimmen. */
export const SCHWELLE_DOPPEL = 0.3
/** Höhenmeter, die mindestens zusammenkommen müssen, bevor „Bergziege" greift. */
export const MIN_HM = 3000

/** Höhenmeter je 100 gewerteten MM — misst, wie bergig jemand unterwegs ist. */
export function hoehenIntensitaet(u: ComparisonUser): number {
  if (u.total_scaled_km <= 0) return 0
  return (u.total_elevation_m / u.total_scaled_km) * 100
}

export function median(werte: number[]): number {
  if (werte.length === 0) return 0
  const s = [...werte].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 === 1 ? s[m] : (s[m - 1] + s[m]) / 2
}

// Spezialdisziplinen mit eigenem Namen; alles Übrige wird zum „Freigeist".
const SPEZIAL_TYPEN: Record<string, { emoji: string; label: string; satz: string }> = {
  wandern: { emoji: '🥾', label: 'Gipfelstürmer', satz: 'der Meter beim Wandern' },
  tanzen: { emoji: '💃', label: 'Tanzbär', satz: 'der Meter auf der Tanzfläche' },
  gehen: { emoji: '🚶', label: 'Flaneur', satz: 'der Meter im Schlenderschritt' },
  ski: { emoji: '🎿', label: 'Schneehase', satz: 'der Meter auf zwei Brettern' },
  inline: { emoji: '🛼', label: 'Rollkünstler', satz: 'der Meter auf Rollen' },
}

function prozent(anteil: number): number {
  return Math.round(anteil * 100)
}

/**
 * Erste zutreffende Regel gewinnt (Reihenfolge wie in der Design-Doku
 * docs/review/profil-designideen.html).
 */
export function bestimmeTyp(
  user: ComparisonUser,
  alle: ComparisonUser[],
  achsen: Achse[],
): Typ {
  const gesamt = user.total_scaled_km
  if (gesamt < MIN_MM)
    return {
      key: 'frischling',
      emoji: '🌱',
      label: 'Frischling',
      satz: 'Noch zu wenige Meter für eine Diagnose — das Netz füllt sich mit jedem Eintrag.',
    }

  const kern = kernSummen(user)
  const spezialAchse = achsen.find((a) => a.key === 'spezial')
  const anteil = {
    lauf: kern.lauf / gesamt,
    rad: kern.rad / gesamt,
    schwimm: kern.schwimm / gesamt,
    spezial: (spezialAchse?.wert ?? 0) / gesamt,
  }

  // Referenz sind die *anderen*: sonst zieht eine einzelne Bergziege in einer
  // kleinen Gruppe den Median gleich selbst über ihre eigene Schwelle.
  const referenz = alle
    .filter((u) => u.user_id !== user.user_id && u.total_scaled_km >= MIN_MM)
    .map(hoehenIntensitaet)
  const eigeneHm = hoehenIntensitaet(user)
  if (user.total_elevation_m >= MIN_HM && eigeneHm >= 2 * median(referenz))
    return {
      key: 'bergziege',
      emoji: '🏔️',
      label: 'Bergziege',
      satz: `${Math.round(eigeneHm)} Höhenmeter je 100 MM — hier geht es fast nur bergauf.`,
    }

  if (anteil.lauf >= 0.2 && anteil.rad >= 0.2 && anteil.schwimm >= 0.2)
    return {
      key: 'triathlon',
      emoji: '🥇',
      label: 'Triathlon-Maschine',
      satz: `Laufen ${prozent(anteil.lauf)} %, Rad ${prozent(anteil.rad)} %, Schwimmen ${prozent(
        anteil.schwimm,
      )} % — drei Disziplinen, kein Schwerpunkt.`,
    }

  if (anteil.schwimm >= SCHWELLE_REIN)
    return {
      key: 'wasserratte',
      emoji: '🐬',
      label: 'Wasserratte',
      satz: `${prozent(anteil.schwimm)} % der Meter im Wasser — hier schwimmt jemand allen davon.`,
    }
  if (anteil.rad >= SCHWELLE_REIN)
    return {
      key: 'kilometerfresser',
      emoji: '🚴',
      label: 'Kilometerfresser',
      satz: `${prozent(anteil.rad)} % der Meter im Sattel.`,
    }
  if (anteil.lauf >= SCHWELLE_REIN)
    return {
      key: 'laufmaschine',
      emoji: '🏃',
      label: 'Laufmaschine',
      satz: `${prozent(anteil.lauf)} % der Meter im Laufschritt.`,
    }

  if (anteil.spezial >= SCHWELLE_REIN && spezialAchse) {
    const def = SPEZIAL_TYPEN[spezialAchse.icon]
    if (def)
      return {
        key: `spezial_${spezialAchse.icon}`,
        emoji: def.emoji,
        label: def.label,
        satz: `${prozent(anteil.spezial)} % ${def.satz}.`,
      }
    return {
      key: 'freigeist',
      emoji: '🧭',
      label: 'Freigeist',
      satz: `${prozent(anteil.spezial)} % der Meter in einer eigenen Disziplin: ${spezialAchse.label}.`,
    }
  }

  const benannt: { label: string; anteil: number }[] = [
    { label: 'Laufen', anteil: anteil.lauf },
    { label: 'Rad', anteil: anteil.rad },
    { label: 'Schwimmen', anteil: anteil.schwimm },
    { label: spezialAchse?.label ?? 'Spezial', anteil: anteil.spezial },
  ].sort((a, b) => b.anteil - a.anteil)
  if (benannt[1].anteil >= SCHWELLE_DOPPEL)
    return {
      key: 'doppelspitze',
      emoji: '⚔️',
      label: 'Doppelspitze',
      satz: `${benannt[0].label} und ${benannt[1].label} halten sich die Waage (${prozent(
        benannt[0].anteil,
      )} % / ${prozent(benannt[1].anteil)} %).`,
    }

  return {
    key: 'allrounder',
    emoji: '🎲',
    label: 'Allrounder',
    satz: `Kein Schwerpunkt — die Meter verteilen sich auf ${user.by_category.length} Sportarten.`,
  }
}
