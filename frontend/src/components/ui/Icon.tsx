type Props = { name: string; size?: number; className?: string; label?: string }

export default function Icon({ name, size = 20, className = '', label }: Props) {
  return (
    <svg
      width={size}
      height={size}
      className={className}
      aria-hidden={label ? undefined : 'true'}
      aria-label={label}
      role={label ? 'img' : undefined}
    >
      <use href={`/icons.svg#${name}`} />
    </svg>
  )
}
