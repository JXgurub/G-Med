import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useClinic } from '../context/ClinicContext';
import { usePharmacy } from '../context/PharmacyContext';
import '../styles/SubscriptionBlockedPage.css';

const SubscriptionBlockedPage = () => {
  const navigate = useNavigate();
  const { clinicOwner } = useClinic();
  const { currentPharmacy } = usePharmacy();

  const isClinicOwner = !!clinicOwner;
  const isPharmacyOwner = !!currentPharmacy;
  const entity = clinicOwner || currentPharmacy;

  useEffect(() => {
    // If no entity loaded, redirect to login
    if (!entity) {
      if (isClinicOwner) {
        navigate('/clinic-owner/login');
      } else if (isPharmacyOwner) {
        navigate('/pharmacy-owner/login');
      } else {
        navigate('/');
      }
    }
  }, [entity, isClinicOwner, isPharmacyOwner, navigate]);

  if (!entity) {
    return null;
  }

  const subscription = entity.subscription;
  const entityType = isClinicOwner ? 'klinika' : 'dorixona';
  const entityName = entity.name;
  const contactPhone = entity.phone_number || 'mavjud emas';
  const contactEmail = entity.email || 'mavjud emas';
  const amount = entity.amount || 'belgilanmagan';

  return (
    <div className="subscription-blocked-container">
      <div className="subscription-blocked-card">
        <div className="blocked-icon">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="80"
            height="80"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line>
          </svg>
        </div>

        <h1 className="blocked-title">Obunangiz muddati tugagan</h1>
        
        <div className="blocked-info">
          <p className="blocked-entity-name">{entityName}</p>
          <p className="blocked-description">
            Sizning {entityType}ingiz obunasi muddati tugagan. 
            Tizimdan foydalanishni davom ettirish uchun obunani yangilang.
          </p>

          {subscription && subscription.end_date && (
            <p className="expiry-date">
              Obuna tugash sanasi: {new Date(subscription.end_date).toLocaleDateString('uz-UZ', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
              })}
            </p>
          )}
        </div>

        <div className="contact-section">
          <h2>Admin bilan bog'laning</h2>
          <div className="contact-details">
            <div className="contact-item">
              <span className="contact-label">📞 Telefon:</span>
              <span className="contact-value">{contactPhone}</span>
            </div>
            <div className="contact-item">
              <span className="contact-label">📧 Email:</span>
              <span className="contact-value">{contactEmail}</span>
            </div>
            {amount && (
              <div className="contact-item">
                <span className="contact-label">💰 Oylik to'lov:</span>
                <span className="contact-value">{Number(amount).toLocaleString()} so'm</span>
              </div>
            )}
          </div>
        </div>

        <div className="action-section">
          <p className="action-instruction">
            To'lovni amalga oshirgandan so'ng, admin sizning obunangizni faollashtiradi.
          </p>
          <button 
            className="logout-button"
            onClick={() => {
              localStorage.clear();
              navigate('/');
            }}
          >
            Chiqish
          </button>
        </div>
      </div>
    </div>
  );
};

export default SubscriptionBlockedPage;
