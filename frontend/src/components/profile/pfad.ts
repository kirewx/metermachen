/** Ziel für alle Personen-Klicks im Vergleich: Profilseite in der Saison `year`. */
export function profilPfad(userId: number, year: number): string {
  return `/profil/${userId}?jahr=${year}`
}
