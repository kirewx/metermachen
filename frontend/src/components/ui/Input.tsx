type Props = React.InputHTMLAttributes<HTMLInputElement> & { label: string }

export default function Input({ label, className = '', ...props }: Props) {
  return (
    <label className={`flex flex-col gap-1 text-xs font-semibold text-ink-mute ${className}`}>
      {label}
      <input
        className="rounded-xl border border-line bg-surface p-2 text-sm font-normal text-ink outline-none focus:border-accent"
        {...props}
      />
    </label>
  )
}
