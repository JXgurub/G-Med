# Frontend Setup Instructions

## Prerequisites

- Node.js (v18 or higher)
- npm or yarn

## Installation

1. Navigate to the frontend directory:
```bash
cd hospitoll_frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create environment file:
```bash
copy .env.example .env
```

4. Update `.env` with your backend API URL if different from default

## Development

Start the development server:
```bash
npm run dev
```

The application will be available at `http://localhost:3000`

## Build for Production

Create an optimized production build:
```bash
npm run build
```

Preview the production build:
```bash
npm run preview
```

## Project Structure

```
src/
├── components/          # Reusable UI components
│   ├── Navbar.jsx      # Top navigation bar
│   └── ClinicCard.jsx  # Clinic display card
├── pages/              # Page components
│   ├── Home.jsx        # Home page with clinic listings
│   └── Login.jsx       # Login page (placeholder)
├── layouts/            # Layout components
│   └── Layout.jsx      # Main layout with navbar
├── dashboards/         # Role-based dashboards (future)
│   ├── patient/
│   ├── doctor/
│   ├── clinic/
│   └── pharmacy/
├── services/           # API services
│   └── api.js          # API utilities and endpoints
├── utils/              # Helper functions
│   └── helpers.js      # Utility functions
├── App.jsx             # Main app component
└── main.jsx            # Entry point
```

## Available Routes

- `/` - Home page (public)
- `/login` - Login page (placeholder)

## Features Implemented

✅ Home page with clinic cards (mock data)
✅ Responsive layout
✅ Navigation bar with Home and Login links
✅ "Men bemorman" (I am a patient) button
✅ Clean, modern UI
✅ Folder structure ready for role-based dashboards

## Next Steps

- Implement authentication with backend
- Connect to real API endpoints
- Build role-based dashboards:
  - Patient dashboard
  - Doctor dashboard
  - Clinic dashboard
  - Pharmacy dashboard
- Add more features (appointments, prescriptions, etc.)
