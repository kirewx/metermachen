import { useState } from 'react'
import IconPicker from './IconPicker'
import { AVATAR_EMOJIS, AVATAR_PIKTOS } from './icons'

type Props = { value: string; onChange: (v: string) => void }

const tab = (aktiv: boolean) =>
  `rounded-full px-3 py-1 text-xs font-bold ${
    aktiv ? 'border border-accent text-accent' : 'text-ink-mute'
  }`

export default function AvatarWahl({ value, onChange }: Props) {
  const [modus, setModus] = useState<'emoji' | 'pikto'>(
    value.startsWith('icon:') ? 'pikto' : 'emoji',
  )
  return (
    <div className="space-y-2">
      <div role="tablist" className="flex gap-1">
        <button type="button" role="tab" className={tab(modus === 'emoji')} onClick={() => setModus('emoji')}>
          Emojis
        </button>
        <button type="button" role="tab" className={tab(modus === 'pikto')} onClick={() => setModus('pikto')}>
          Piktogramme
        </button>
      </div>
      {modus === 'emoji' ? (
        <div className="flex flex-wrap gap-1">
          {AVATAR_EMOJIS.map((e) => (
            <button
              key={e}
              type="button"
              onClick={() => onChange(e)}
              className={`flex h-9 w-9 items-center justify-center rounded-xl border text-lg ${
                value === e ? 'border-accent shadow-glow' : 'border-line'
              }`}
            >
              {e}
            </button>
          ))}
        </div>
      ) : (
        <IconPicker
          auswahl={AVATAR_PIKTOS}
          value={value.replace('icon:', '')}
          onChange={(name) => onChange(`icon:${name}`)}
        />
      )}
    </div>
  )
}
