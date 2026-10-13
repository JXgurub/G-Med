import DoctorCard from './DoctorCard'
import './ClinicDoctors.css'

const ClinicDoctors = ({ doctors }) => {
  return (
    <section className="clinic-doctors">
      <div className="container">
        <h2>Doktorlar</h2>
        <p className="section-subtitle">Bizning mutaxassis doktorlar jamoasi</p>

        <div className="doctors-grid">
          {doctors && doctors.map((doctor) => (
            <DoctorCard key={doctor.id} doctor={doctor} />
          ))}
        </div>
      </div>
    </section>
  )
}

export default ClinicDoctors
