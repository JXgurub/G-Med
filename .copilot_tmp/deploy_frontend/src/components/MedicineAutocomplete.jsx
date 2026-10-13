import { useState, useRef, useEffect } from 'react'
import { medicinesApi } from '../services/api'
import './MedicineAutocomplete.css'

const DOSAGE_FORM_LABELS = {
  tablet: 'Tabletka', tabletka: 'Tabletka',
  capsule: 'Kapsula', capsules: 'Kapsula',
  syrup: 'Suyuqlik', liquid: 'Suyuqlik',
  injection: 'Inyeksiya', injectable: 'Inyeksiya',
  cream: 'Krem', ointment: 'Malham',
  drops: 'Tomchi', powder: 'Kukun',
}

const formatDosageForm = (form) => {
  if (!form) return ''
  return DOSAGE_FORM_LABELS[form.toLowerCase()] || form
}

const CHIP_COLORS = [
  { bg: '#e8f5e9', border: '#4caf50', text: '#2e7d32' },
  { bg: '#e3f2fd', border: '#2196f3', text: '#1565c0' },
  { bg: '#fce4ec', border: '#e91e63', text: '#880e4f' },
  { bg: '#fff3e0', border: '#ff9800', text: '#e65100' },
  { bg: '#ede7f6', border: '#7e57c2', text: '#4527a0' },
  { bg: '#e0f7fa', border: '#00bcd4', text: '#006064' },
]

const MedicineAutocomplete = ({ value = '', onChange, placeholder = 'Dori nomini yozing...' }) => {
  const [inputValue, setInputValue] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [loading, setLoading] = useState(false)
  const [highlightedIndex, setHighlightedIndex] = useState(-1)
  const [selectedMedicines, setSelectedMedicines] = useState([])
  const inputRef = useRef(null)
  const wrapperRef = useRef(null)
  const searchTimeoutRef = useRef(null)

  useEffect(() => {
    if (typeof value === 'string') {
      const medicines = value.split(',').map((m) => m.trim()).filter((m) => m.length > 0)
      setSelectedMedicines(medicines)
    } else {
      setSelectedMedicines([])
    }
  }, [value])

  const searchMedicines = async (query) => {
    if (!query || query.length < 1) {
      setSuggestions([])
      setShowSuggestions(false)
      return
    }
    setLoading(true)
    try {
      const results = await medicinesApi.search(query, 10)
      setSuggestions(Array.isArray(results) ? results : [])
      setHighlightedIndex(-1)
      setShowSuggestions(true)
    } catch {
      setSuggestions([])
    } finally {
      setLoading(false)
    }
  }

  const handleInputChange = (e) => {
    const val = e.target.value
    setInputValue(val)
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current)
    searchTimeoutRef.current = setTimeout(() => searchMedicines(val), 280)
  }

  const formatMedicineName = (medicine) => {
    const parts = [medicine.name]
    if (medicine.strength) parts.push(`(${medicine.strength})`)
    if (medicine.dosage_form) parts.push(formatDosageForm(medicine.dosage_form))
    return parts.join(' ')
  }

  const handleSelectMedicine = (medicine) => {
    const name = formatMedicineName(medicine)
    if (!selectedMedicines.includes(name)) {
      const updated = [...selectedMedicines, name]
      setSelectedMedicines(updated)
      onChange({ target: { value: updated.join(', ') } })
    }
    setInputValue('')
    setSuggestions([])
    setShowSuggestions(false)
    setHighlightedIndex(-1)
    inputRef.current?.focus()
  }

  const handleRemoveMedicine = (index) => {
    const updated = selectedMedicines.filter((_, i) => i !== index)
    setSelectedMedicines(updated)
    onChange({ target: { value: updated.join(', ') } })
  }

  const handleKeyDown = (e) => {
    if (!showSuggestions || suggestions.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlightedIndex((prev) => Math.min(prev + 1, suggestions.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlightedIndex((prev) => Math.max(prev - 1, 0))
    } else if (e.key === 'Enter' && highlightedIndex >= 0) {
      e.preventDefault()
      handleSelectMedicine(suggestions[highlightedIndex])
    } else if (e.key === 'Escape') {
      setShowSuggestions(false)
    }
  }

  useEffect(() => {
    const handleOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [])

  return (
    <div className="mac-wrapper" ref={wrapperRef}>
      {/* Input row */}
      <div className={`mac-input-row${showSuggestions && suggestions.length > 0 ? ' mac-input-row--open' : ''}`}>
        <span className="mac-icon">💊</span>
        <input
          ref={inputRef}
          type="text"
          placeholder={placeholder}
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => inputValue.length > 0 && suggestions.length > 0 && setShowSuggestions(true)}
          className="mac-input"
          autoComplete="off"
        />
        {loading
          ? <span className="mac-spinner" />
          : inputValue.length > 0
            ? <button type="button" className="mac-clear-input" onClick={() => { setInputValue(''); setSuggestions([]); setShowSuggestions(false); inputRef.current?.focus() }}>✕</button>
            : null
        }
      </div>

      {/* Dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="mac-dropdown">
          <div className="mac-dropdown-header">Topilgan dorilar</div>
          {suggestions.map((medicine, idx) => (
            <div
              key={medicine.id}
              className={`mac-suggestion-item${idx === highlightedIndex ? ' mac-suggestion-item--active' : ''}`}
              onMouseDown={(e) => { e.preventDefault(); handleSelectMedicine(medicine) }}
              onMouseEnter={() => setHighlightedIndex(idx)}
            >
              <div className="mac-sugg-left">
                <div className="mac-sugg-name">{medicine.name}</div>
                {medicine.generic_name && (
                  <div className="mac-sugg-generic">{medicine.generic_name}</div>
                )}
              </div>
              <div className="mac-sugg-right">
                {medicine.strength && (
                  <span className="mac-badge mac-badge--strength">{medicine.strength}</span>
                )}
                {medicine.dosage_form && (
                  <span className="mac-badge mac-badge--form">{formatDosageForm(medicine.dosage_form)}</span>
                )}
                {medicine.category && medicine.category !== 'Boshqa' && (
                  <span className="mac-badge mac-badge--category">{medicine.category}</span>
                )}
              </div>
            </div>
          ))}
          <div className="mac-dropdown-footer">{suggestions.length} ta natija</div>
        </div>
      )}

      {showSuggestions && !loading && suggestions.length === 0 && inputValue.length > 1 && (
        <div className="mac-dropdown">
          <div className="mac-empty">"<strong>{inputValue}</strong>" uchun dori topilmadi</div>
        </div>
      )}

      {/* Selected chips */}
      {selectedMedicines.length > 0 && (
        <div className="mac-chips-wrap">
          <div className="mac-chips-label">Tanlangan: {selectedMedicines.length} ta dori</div>
          <div className="mac-chips">
            {selectedMedicines.map((med, index) => {
              const color = CHIP_COLORS[index % CHIP_COLORS.length]
              return (
                <div
                  key={`${med}-${index}`}
                  className="mac-chip"
                  style={{ background: color.bg, borderColor: color.border, color: color.text }}
                >
                  <span className="mac-chip-num" style={{ background: color.border, color: '#fff' }}>{index + 1}</span>
                  <span className="mac-chip-text">{med}</span>
                  <button
                    type="button"
                    className="mac-chip-remove"
                    style={{ color: color.text }}
                    onClick={() => handleRemoveMedicine(index)}
                    aria-label="O'chirish"
                  >
                    ✕
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export default MedicineAutocomplete
