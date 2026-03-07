# Hospitoll Frontend

React-based frontend for the Hospitoll healthcare platform.

## Tech Stack

- React 18
- Vite
- React Router v6

## Getting Started

1. Install dependencies:
```bash
npm install
```

2. Run development server:
```bash
npm run dev
```

3. Build for production:
```bash
npm run build
```

## Project Structure

```
src/
├── components/       # Reusable components
├── pages/           # Page components
├── layouts/         # Layout components
├── dashboards/      # Role-based dashboard components
│   ├── patient/
│   ├── doctor/
│   ├── clinic/
│   └── pharmacy/
├── services/        # API services
├── utils/           # Utility functions
└── App.jsx          # Main app component
```

## Features

- Public home page with clinic listings
- Authentication (login/register)
- Role-based dashboards (future)
