import { Navigate } from 'react-router-dom'
import { getPreferredLoginPath } from '../utils/loginPortalPreference'

const LoginRedirect = () => {
  return <Navigate to={getPreferredLoginPath()} replace />
}

export default LoginRedirect
