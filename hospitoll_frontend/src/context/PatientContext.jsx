import { createContext, useContext, useEffect, useState } from 'react'
import { authApi, patientsApi, medicalRecordsApi, doctorsApi, clinicsApi } from '../services/api'

const PatientContext = createContext()

const parseMedicationList = (value) => {
  return String(value || '')
    .split(/[\n,;]+/)
    .map((item) => item.replace(/^[-•\d.)\s]+/, '').trim())
    .filter(Boolean)
}

// Helper function to map API patient data to local format
const mapPatientProfile = (patient, user) => {
  return {
    id: patient.id,
    passportId: patient.national_id || '',
    fullName: user.full_name || `${user.first_name} ${user.last_name}`.trim(),
    birthDate: patient.date_of_birth || '',
    birthYear: patient.birth_year || '',
    phone: user.phone_number || patient.phone_number || '',
    email: user.email || '',
    city: patient.city || patient.address || '',
    gender: patient.gender || '',
    age: patient.age || '',
    bloodType: patient.blood_type || '',
    weightKg: patient.weight_kg || '',
    heightCm: patient.height_cm || '',
    drugAllergies: patient.drug_allergies || '',
    animalAllergies: patient.animal_allergies || ''
  }
}

// Helper function to map medical records to patient history
const buildPatientHistory = async (medicalRecords) => {
  const history = []
  // Ensure medicalRecords is an array
  const records = Array.isArray(medicalRecords) ? medicalRecords : []
  for (const record of records) {
    try {
      // Get doctor name from API response - it now includes doctor_name and doctor_specialization
      const doctorName = record.doctor_name || (record.doctor_details?.full_name) || 'Noma\'lum shifokor'
      const doctorSpecialization = record.doctor_specialization && Array.isArray(record.doctor_specialization) 
        ? record.doctor_specialization[0] 
        : (record.doctor_details?.specializations?.[0] || '')
      
      // Get clinic name from API response
      const clinicName = record.clinic_name || (record.clinic_details?.name) || 'Noma\'lum klinika'

      history.push({
        id: record.id,
        date: record.created_at?.split('T')[0] || record.visit_date,
        diagnosis: record.assessment || record.diagnosis || 'Ko\'rik amalga oshirildi',
        complaint: record.chief_complaint || record.reason || '',
        doctorId: record.doctor,
        doctorName: doctorName,
        doctorSpecialization: doctorSpecialization,
        clinic: clinicName,
        medications: parseMedicationList(record.plan)
      })
    } catch (error) {
      console.error('Error building history entry:', error)
    }
  }
  return history.sort((a, b) => new Date(b.date) - new Date(a.date))
}

// Helper function to get unique doctors from records
const extractDoctors = async (medicalRecords) => {
  const doctorMap = new Map()
  // Ensure medicalRecords is an array
  const records = Array.isArray(medicalRecords) ? medicalRecords : []

  for (const record of records) {
    if (record.doctor && !doctorMap.has(record.doctor)) {
      try {
        // Use doctor_name from API response
        const doctorName = record.doctor_name || 'Noma\'lum shifokor'
        const specialization = record.doctor_specialization && Array.isArray(record.doctor_specialization)
          ? record.doctor_specialization[0]
          : 'Umumiy tabib'

        doctorMap.set(record.doctor, {
          id: record.doctor,
          name: doctorName,
          specialization: specialization,
          clinic: 'Klinika',
          rating: 0 // Default rating
        })
      } catch (error) {
        console.error('Error extracting doctor:', error)
      }
    }
  }

  return Array.from(doctorMap.values())
}

export const PatientProvider = ({ children }) => {
  const [patientAuth, setPatientAuth] = useState(null)
  const [patientData, setPatientData] = useState({
    profile: null,
    history: [],
    doctors: [],
    ratings: {},
    lastUpdated: null
  })
  const [loading, setLoading] = useState(true)

  // Check for existing authentication on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token')
      const userRole = localStorage.getItem('user_role')

      if (token && userRole === 'patient') {
        try {
          await loadPatientData()
        } catch (error) {
          console.error('Failed to load patient data:', error)
          logoutPatient()
        }
      }
      setLoading(false)
    }

    checkAuth()
  }, [])

  const loadPatientData = async () => {
    try {
      // Get patient profile
      const patient = await patientsApi.getMy()
      const user = patient.user || patient.user_details

      if (!user) {
        throw new Error('User data not found')
      }

      const profile = mapPatientProfile(patient, user)

      // Get medical records for this patient
      const medicalRecordsResponse = await medicalRecordsApi.getAll({ patient: patient.id })
      const medicalRecords = medicalRecordsResponse?.results || medicalRecordsResponse || []

      // Build patient data
      const history = await buildPatientHistory(medicalRecords)
      const doctors = await extractDoctors(medicalRecords)

      // Get existing ratings for this patient
      const ratingsMap = {}
      try {
        const ratingsResponse = await doctorsApi.getRatings({ patient: patient.id })
        const ratingsData = ratingsResponse?.results || ratingsResponse || []
        
        // Map ratings by doctor ID
        ratingsData.forEach(rating => {
          ratingsMap[rating.doctor] = {
            id: rating.id,
            value: rating.rating
          }
        })
      } catch (error) {
        console.error('Error loading ratings:', error)
      }

      const auth = {
        patientId: patient.id,
        fullName: profile.fullName,
        email: user.email,
        phone: user.phone_number || patient.phone_number || ''
      }

      setPatientAuth(auth)
      setPatientData({
        profile,
        history,
        doctors,
        ratings: ratingsMap,
        lastUpdated: new Date().toLocaleString('uz-UZ')
      })
    } catch (error) {
      console.error('Error loading patient data:', error)
      throw error
    }
  }

  const loginPatient = async (phoneNumber, password) => {
    try {
      const response = await authApi.patientLogin({ 
        phone_number: phoneNumber,
        password 
      })

      if (response.user.role !== 'patient') {
        return { success: false, error: 'Bu hisob bemor hisobi emas' }
      }

      // Store tokens and role
      localStorage.setItem('access_token', response.access)
      localStorage.setItem('refresh_token', response.refresh)
      localStorage.setItem('user_role', response.user.role)

      // Load patient data
      await loadPatientData()

      return { success: true }
    } catch (error) {
      console.error('Login error:', error)
      return { success: false, error: 'Telefon raqam yoki parol noto\'g\'ri' }
    }
  }

  const logoutPatient = () => {
    setPatientAuth(null)
    setPatientData({
      profile: null,
      history: [],
      doctors: [],
      ratings: {},
      lastUpdated: null
    })
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_role')
  }

  const updateDoctorRating = async (doctorId, rating) => {
    try {
      // Get current patient ID from profile
      const patientId = patientData.profile?.id
      
      if (!patientId) {
        console.error('Patient ID not found')
        alert('Bemor ma\'lumotlari topilmadi')
        return
      }

      // Check if rating already exists
      const existingRatingId = patientData.ratings[doctorId]?.id

      if (existingRatingId) {
        // Update existing rating
        await doctorsApi.updateRating(existingRatingId, {
          doctor: doctorId,
          patient: patientId,
          rating: rating,
          comment: '',
          is_anonymous: false
        })
      } else {
        // Create new rating
        await doctorsApi.addRating({
          doctor: doctorId,
          patient: patientId,
          rating: rating,
          comment: '',
          is_anonymous: false
        })
      }

      // Update local state
      setPatientData((prev) => ({
        ...prev,
        ratings: {
          ...prev.ratings,
          [doctorId]: { id: existingRatingId, value: rating }
        },
        lastUpdated: new Date().toLocaleString('uz-UZ')
      }))

      alert(`✓ Doktorga ${rating}/5 baho berildi!`)
      
      // Reload data to get updated doctor ratings
      await loadPatientData()
    } catch (error) {
      console.error('Rating update error:', error)
      if (error.response?.data?.non_field_errors?.[0]?.includes('allaqachon')) {
        alert('Siz bu doktorga allaqachon baho berdingiz')
      } else {
        alert('Baho berishda xatolik yuz berdi')
      }
    }
  }

  const updatePatientProfile = async (payload) => {
    const patientId = patientData.profile?.id
    if (!patientId) {
      throw new Error('Bemor maʼlumotlari topilmadi')
    }

    const normalizeDecimal = (value) => {
      if (value === null || value === undefined || value === '') return null
      const numeric = Number(value)
      if (!Number.isFinite(numeric) || numeric < 0) return null
      return numeric
    }

    const updatePayload = {
      blood_type: payload.bloodType || '',
      date_of_birth: payload.birthDate || null,
      weight_kg: normalizeDecimal(payload.weightKg),
      height_cm: normalizeDecimal(payload.heightCm),
      drug_allergies: (payload.drugAllergies || '').trim(),
      animal_allergies: (payload.animalAllergies || '').trim()
    }

    await patientsApi.update(patientId, updatePayload)
    await loadPatientData()
  }

  const changePatientPassword = async (currentPassword, newPassword) => {
    await authApi.changePassword(currentPassword, newPassword)
  }

  if (loading) {
    return null
  }

  return (
    <PatientContext.Provider value={{ patientAuth, patientData, updateDoctorRating, updatePatientProfile, changePatientPassword, loginPatient, logoutPatient }}>
      {children}
    </PatientContext.Provider>
  )
}

export const usePatient = () => {
  const context = useContext(PatientContext)
  if (!context) {
    throw new Error('usePatient must be used within PatientProvider')
  }
  return context
}
