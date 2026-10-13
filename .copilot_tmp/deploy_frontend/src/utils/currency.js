const extractDigits = (value) => String(value ?? '').replace(/\D/g, '')

export const formatCurrencyInput = (value) => {
  const digits = extractDigits(value)
  if (!digits) return ''
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
}

export const parseCurrencyInput = (value) => {
  const digits = extractDigits(value)
  if (!digits) return 0
  return Number(digits)
}