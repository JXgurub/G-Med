import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import ClinicHeader from '../components/ClinicHeader'
import ClinicServices from './ClinicServices'
import ClinicDoctors from '../components/ClinicDoctors'
import api, { clinicsApi, doctorsApi, resolveMediaUrl } from '../services/api'
import './ClinicPublic.css'

const ClinicPublic = () => {
  const { id } = useParams()
  const [clinic, setClinic] = useState(null)
  const [doctors, setDoctors] = useState([])
  const [services, setServices] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadClinic = async () => {
      try {
        const clinicData = await clinicsApi.getById(id, { _ts: Date.now() })
        setClinic({
          id: clinicData.id,
          name: clinicData.name,
          bannerImage: resolveMediaUrl(clinicData.banner_image),
          rating: clinicData.rating || 0,
          reviewCount: clinicData.total_ratings || 0,
          address: clinicData.address || '',
          phone: clinicData.phone_number || '',
          workingHours: clinicData.working_hours || clinicData.workingHours || '09:00 - 18:00',
          city: clinicData.address || '',
          description: clinicData.description || ''
        })

        const [doctorData, serviceData] = await Promise.all([
          doctorsApi.getAll({ clinic: clinicData.id }),
          api.get('/clinics/services/', { clinic: clinicData.id })
        ])
        const results = doctorData?.results || doctorData || []
        const mappedDoctors = results
          .filter((doctor) => doctor?.is_active !== false)
          .map((doctor) => ({
          id: doctor.id,
          fullName: doctor.user
            ? `${doctor.user.first_name || ''} ${doctor.user.last_name || ''}`.trim()
            : 'Doktor',
          specialization: doctor.specializations?.map((s) => s.name).join(', ') || 'N/A',
          rating: doctor.rating || 0,
          displayOrder: Number(doctor.display_order || 0)
          }))
        mappedDoctors.sort((left, right) => {
          if (left.displayOrder !== right.displayOrder) {
            return left.displayOrder - right.displayOrder
          }
          return String(left.fullName || '').localeCompare(String(right.fullName || ''))
        })
        setDoctors(mappedDoctors)
        setServices(serviceData?.results || serviceData || [])
      } catch (error) {
        setClinic(null)
        setDoctors([])
        setServices([])
      } finally {
        setLoading(false)
      }
    }

    loadClinic()
  }, [id])

  if (loading) {
    return <div className="clinic-public-loading">Yuklanmoqda...</div>
  }

  if (!clinic) {
    return <div className="clinic-public-loading">Klinika topilmadi.</div>
  }

  return (
    <div className="clinic-public">
      <ClinicHeader clinic={clinic} />
      <ClinicServices services={services} />
      <ClinicDoctors clinicId={clinic.id} doctors={doctors} />
    </div>
  )
}

export default ClinicPublic
