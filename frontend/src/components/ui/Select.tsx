type Props = React.SelectHTMLAttributes<HTMLSelectElement> & { label: string }

export default function Select({ label, className = '', children, ...props }: Props) {
  return (
    <label className={`flex flex-col gap-1 text-xs font-semibold text-ink-mute ${className}`}>
      {label}
      <select
        className="rounded-xl border border-line bg-surface p-2 text-sm font-normal text-ink outline-none focus:border-accent"
        {...props}
      >
        {children}
      </select>
    </label>
  )
}
