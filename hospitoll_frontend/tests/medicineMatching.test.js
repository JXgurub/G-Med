import assert from 'node:assert/strict'
import test from 'node:test'
import {
  findAvailableMedicineMatch,
  medicineMatches,
  medicineSearchMatches,
} from '../src/utils/medicineMatching.js'

test('finds an in-stock batch even when an empty batch appears first', () => {
  const inventory = [
    { name: 'Amoksitsillin', strength: '500 mg', stock: 0 },
    { name: 'Amoksitsillin', strength: '500 mg', stock: 6 },
  ]

  assert.equal(findAvailableMedicineMatch(inventory, 'Amoksitsillin 500 mg')?.stock, 6)
})

test('matches a prescription ingredient against the pharmacy brand generic name', () => {
  const medicine = {
    name: 'Glyukofaj',
    generic_name: 'Metformin',
    strength: '500 mg',
    stock: 4,
  }

  assert.equal(medicineMatches('Metformin 500 mg', medicine), true)
  assert.equal(medicineMatches('Metformin 500mg', medicine), true)
})

test('does not match a different strength or a partial medicine name', () => {
  assert.equal(medicineMatches('Metformin 500 mg', {
    name: 'Glyukofaj',
    generic_name: 'Metformin',
    strength: '850 mg',
    stock: 4,
  }), false)
  assert.equal(medicineMatches('para', { name: 'Paratsetamol', stock: 4 }), false)
  assert.equal(medicineSearchMatches('para', { name: 'Paratsetamol', stock: 4 }), true)
})
