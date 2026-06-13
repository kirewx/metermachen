import Icon from './Icon'

type Props = { auswahl: readonly string[]; value: string; onChange: (v: string) => void }

export default function IconPicker({ auswahl, value, onChange }: Props) {
  return (
    <div className="flex flex-wrap gap-1">
      {auswahl.map((name) => (
        <button
          key={name}
          type="button"
          aria-label={name}
          onClick={() => onChange(name)}
          className={`flex h-9 w-9 items-center justify-center rounded-xl border transition ${
            value === name
              ? 'border-accent text-accent shadow-glow'
              : 'border-line text-ink-mute hover:text-ink'
          }`}
        >
          <Icon name={name} />
        </button>
      ))}
    </div>
  )
}
