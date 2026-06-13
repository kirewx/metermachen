import Icon from './Icon'

type Props = { open: boolean; onClose: () => void; title: string; children: React.ReactNode }

export default function Modal({ open, onClose, title, children }: Props) {
  if (!open) return null
  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-label={title}
        className="w-full max-w-md rounded-2xl border border-line bg-card p-5 shadow-glow"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-black text-ink">{title}</h2>
          <button aria-label="Schließen" onClick={onClose} className="text-ink-mute hover:text-ink">
            <Icon name="x" size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
