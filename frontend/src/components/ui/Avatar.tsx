import Icon from './Icon'

const box = { sm: 'h-6 w-6 text-sm', md: 'h-8 w-8 text-lg', lg: 'h-12 w-12 text-2xl' }
const icon = { sm: 14, md: 18, lg: 26 }

type Props = { value: string; size?: keyof typeof box }

export default function Avatar({ value, size = 'md' }: Props) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-full border border-line bg-card ${box[size]}`}
    >
      {value.startsWith('icon:') ? (
        <Icon name={value.slice(5)} size={icon[size]} className="text-accent" />
      ) : (
        <span>{value}</span>
      )}
    </span>
  )
}
