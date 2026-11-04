/** ["Ben"] → "Ben"; ["Ben","Clara","David"] → "Ben, Clara und David" */
export function undListe(namen: string[]): string {
  if (namen.length <= 1) return namen[0] ?? ''
  return `${namen.slice(0, -1).join(', ')} und ${namen[namen.length - 1]}`
}
