import { useState } from 'react'
import './PasswordInput.css'

const EyeIcon = ({ open }) => (
  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" className="password-eye-icon">
    {open ? (
      <>
        <path d="M2 2l20 20" />
        <path d="M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 10 8 10 8a18.86 18.86 0 0 1-3.33 4.55" />
        <path d="M6.61 6.61A18.67 18.67 0 0 0 2 12s3 8 10 8a10.94 10.94 0 0 0 4.24-.86" />
        <path d="M9.88 9.88A3 3 0 0 0 12 15a2.97 2.97 0 0 0 2.12-.88" />
      </>
    ) : (
      <>
        <path d="M2 12s3-8 10-8 10 8 10 8-3 8-10 8-10-8-10-8z" />
        <circle cx="12" cy="12" r="3" />
      </>
    )}
  </svg>
)

const PasswordInput = ({
  className = '',
  wrapperClassName = '',
  buttonClassName = '',
  showLabel = 'Parolni ko\'rsatish',
  hideLabel = 'Parolni yashirish',
  ...props
}) => {
  const [isVisible, setIsVisible] = useState(false)

  return (
    <div className={`password-input-wrapper ${wrapperClassName}`.trim()}>
      <input
        {...props}
        type={isVisible ? 'text' : 'password'}
        className={`${className} password-input-control`.trim()}
      />
      <button
        type="button"
        className={`password-toggle-button ${isVisible ? 'is-visible' : ''} ${buttonClassName}`.trim()}
        onClick={() => setIsVisible((prev) => !prev)}
        aria-label={isVisible ? hideLabel : showLabel}
        title={isVisible ? hideLabel : showLabel}
        aria-pressed={isVisible}
      >
        <EyeIcon open={isVisible} />
      </button>
    </div>
  )
}

export default PasswordInput