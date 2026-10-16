const normalizeMedicineText = (value) => String(value || '')
  .toLocaleLowerCase()
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .replace(/[^\p{L}\p{N}]+/gu, ' ')
  .replace(/\s+/g, ' ')
  .trim()

const medicineStrength = (value) => {
  const match = String(value || '').toLowerCase().match(/(\d+(?:[.,]\d+)?)\s*(mcg|µg|μg|ug|mg|g|ml|l|iu|%)(?=\s|\/|$)/i)
  if (!match) return ''

  const amount = Number(match[1].replace(',', '.'))
  const unit = match[2].toLowerCase()
  if (['mcg', 'µg', 'μg', 'ug'].includes(unit)) return `mass:${amount / 1000}`
  if (unit === 'g') return `mass:${amount * 1000}`
  if (unit === 'mg') return `mass:${amount}`
  if (unit === 'l') return `volume:${amount * 1000}`
  if (unit === 'ml') return `volume:${amount}`
  return `${unit}:${amount}`
}

const getMedicineAliases = (medicine) => {
  if (typeof medicine === 'string') return [medicine]

  const name = medicine?.name || medicine?.medicine_name || ''
  const genericName = medicine?.generic_name || ''
  const strength = medicine?.strength || medicine?.medicine_strength || ''

  return [...new Set([
    name,
    genericName,
    [name, strength].filter(Boolean).join(' '),
    [genericName, strength].filter(Boolean).join(' '),
  ].map((alias) => String(alias).trim()).filter(Boolean))]
}

const isPhraseMatch = (first, second) => {
  const normalizedFirst = normalizeMedicineText(first)
  const normalizedSecond = normalizeMedicineText(second)
  if (!normalizedFirst || !normalizedSecond) return false

  const firstStrength = medicineStrength(first)
  const secondStrength = medicineStrength(second)
  if (firstStrength && secondStrength && firstStrength !== secondStrength) return false

  return normalizedFirst === normalizedSecond
    || ` ${normalizedFirst} `.includes(` ${normalizedSecond} `)
    || ` ${normalizedSecond} `.includes(` ${normalizedFirst} `)
}

export const medicineMatches = (requestedName, medicine) => {
  const candidateStrength = medicineStrength(
    typeof medicine === 'string'
      ? medicine
      : [
        medicine?.name,
        medicine?.medicine_name,
        medicine?.generic_name,
        medicine?.strength,
        medicine?.medicine_strength,
      ].filter(Boolean).join(' ')
  )
  const requestedStrength = medicineStrength(requestedName)
  if (requestedStrength && candidateStrength && requestedStrength !== candidateStrength) return false

  return getMedicineAliases(medicine).some((alias) => isPhraseMatch(requestedName, alias))
}

export const medicineSearchMatches = (query, medicine) => {
  const normalizedQuery = normalizeMedicineText(query)
  if (!normalizedQuery) return true

  return getMedicineAliases(medicine).some((alias) => (
    normalizeMedicineText(alias).includes(normalizedQuery)
  ))
}

export const findAvailableMedicineMatch = (medicines, requestedName) => (
  (Array.isArray(medicines) ? medicines : []).find((medicine) => (
    Number(medicine?.stock ?? medicine?.quantity_in_stock ?? 0) > 0
    && medicineMatches(requestedName, medicine)
  )) || null
)

export const getMedicineSearchNames = (medicine) => getMedicineAliases(medicine)
