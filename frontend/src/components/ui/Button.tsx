type Variant = 'primary' | 'ghost' | 'danger'

const styles: Record<Variant, string> = {
  primary:
    'bg-accent font-black text-accent-ink shadow-glow-strong hover:brightness-110 disabled:opacity-40 disabled:shadow-none',
  ghost: 'border border-line text-ink-soft hover:border-accent hover:text-accent',
  danger: 'border border-danger text-danger hover:bg-danger/10',
}

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }

export default function Button({ variant = 'primary', className = '', ...props }: Props) {
  return (
    <button
      className={`rounded-xl px-4 py-2 text-sm transition ${styles[variant]} ${className}`}
      {...props}
    />
  )
}
