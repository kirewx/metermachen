type Props = { name: string; size?: number; className?: string }

export default function Icon({ name, size = 20, className = '' }: Props) {
  return (
    <svg width={size} height={size} className={className} aria-hidden="true">
      <use href={`/icons.svg#${name}`} />
    </svg>
  )
}
