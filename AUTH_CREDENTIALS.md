# Hospitoll Platform - Authentication Credentials

## Status
✅ **All authentication flows are working**

### Admin Account
- **Email**: admin@example.com
- **Password**: <set-in-your-local-db>
- **Role**: admin (SuperUser)
- **Access**: Admin Dashboard at `/admin-dashboard`

### Clinic Owner Account
- **Email**: clinic.owner@example.com
- **Password**: <set-in-your-local-db>
- **Role**: clinic
- **Access**: Clinic Owner Dashboard at `/clinic-owner-dashboard`

### Pharmacy Owner Account
- **Email**: pharmacy.owner@example.com
- **Password**: <set-in-your-local-db>
- **Role**: pharmacy
- **Access**: Pharmacy Owner Dashboard at `/pharmacy-owner-dashboard`

### Doctor Account
- **Email**: doctor@example.com
- **Password**: (needs to be set by clinic owner)
- **Role**: doctor
- **Access**: Doctor Dashboard at `/doctor-dashboard`

### Patient Accounts
- **Email**: patient@example.com
- **Auth Method**: Passport ID + Password (NOT email)
- **Role**: patient
- **Access**: Patient Portal at `/patient-portal`

## Authentication Endpoints

### Email-based Authentication
```
POST /api/v1/users/token/
Content-Type: application/json

{
  "email": "email@example.com",
  "password": "password123"
}
```
**Used by**: Admin, Clinic Owner, Pharmacy Owner, Doctor
**Returns**: `access_token`, `refresh_token`, `user` object with role

### Passport ID Authentication
```
POST /api/v1/users/patient-token/
Content-Type: application/json

{
  "passport_id": "AA123456",
  "password": "password123"
}
```
**Used by**: Patients
**Returns**: `access_token`, `refresh_token`, `user` object

### Get Current User Profile
```
GET /api/v1/users/profile/
Authorization: Bearer <access_token>
```
**Returns**: Current user details with role

## Frontend Login Pages

| User Type | URL | Method |
|-----------|-----|--------|
| Admin | `/admin-login` | Email/Password |
| Clinic Owner | `/clinic-owner-login` | Email/Password |
| Pharmacy Owner | `/pharmacy-owner-login` | Email/Password |
| Doctor | `/doctor-login` | Email/Password |
| Patient | `/patient-login` | Passport ID/Password |

## Recent Fixes

### Issue: Pharmacy Owner Login (401 Unauthorized)
**Problem**: After admin created pharmacy with owner credentials, the pharmacy owner could not login with those credentials.

**Root Cause**: The initial pharmacy owner test account had an incorrect password hash in the database.

**Solution**: Reset the pharmacy owner password to a known value (`lalo123`) and verified the password hashing works correctly through:
1. Tested password verification with `CustomUser.check_password()`
2. Fixed password using `CustomUser.set_password()`
3. Verified new pharmacy creation with password works correctly

### Verification Tests
✅ Admin login works: use your local seeded admin account
✅ Clinic owner login works: use your local seeded clinic owner account
✅ Pharmacy owner login works: use your local seeded pharmacy owner account
✅ New pharmacy creation: Creates user with correct password
✅ Patient login works: Uses passport ID instead of email

## Testing the Authentication Flow

### Test Clinic Owner Login
```bash
curl -X POST http://localhost:8000/api/v1/users/token/ \
  -H "Content-Type: application/json" \
  -d '{"email":"clinic.owner@example.com","password":"<password>"}'
```

### Test Pharmacy Owner Login
```bash
curl -X POST http://localhost:8000/api/v1/users/token/ \
  -H "Content-Type: application/json" \
  -d '{"email":"pharmacy.owner@example.com","password":"<password>"}'
```

### Test Patient Login
```bash
curl -X POST http://localhost:8000/api/v1/users/patient-token/ \
  -H "Content-Type: application/json" \
  -d '{"passport_id":"AB123456","password":"patient_password"}'
```

## Database Structure

### CustomUser Model
- `email`: Unique email address
- `username`: Set to email
- `password`: Django PBKDF2-SHA256 hashed
- `role`: One of ['admin', 'clinic', 'doctor', 'patient', 'pharmacy']
- `is_active`: Should be True for login
- `is_superuser`: True for admin, False for others

### Clinic Model
- `owner`: OneToOneField to CustomUser (role='clinic')
- Owner created automatically when clinic is created

### Pharmacy Model
- `owner`: OneToOneField to CustomUser (role='pharmacy')
- Owner created automatically when pharmacy is created

### Patient Model
- `user`: OneToOneField to CustomUser (role='patient')
- `national_id`: Passport ID for patient login
- User created automatically when patient is created

## API Response Format

### Successful Login (200 OK)
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "username": "user@example.com",
    "first_name": "First",
    "last_name": "Last",
    "role": "clinic",
    "phone_number": "+998...",
    "is_active": true,
    "is_verified": false
  }
}
```

### Failed Login (401 Unauthorized)
```json
{
  "detail": "Email yoki parol noto'g'ri"
}
```

## Next Steps

1. **Password Reset Flow**: Implement password reset for users
2. **Doctor Creation**: Allow clinic owners to create doctors (currently needs backend implementation)
3. **Audit Logging**: Log all login attempts for security
4. **Two-Factor Authentication**: Add 2FA for sensitive roles (admin, clinic owner)
5. **Email Verification**: Verify email addresses for new accounts
