# LoA Worker Dashboard

Professional Next.js dashboard for monitoring and managing Letters of Authority processing.

## Features

- **Dashboard Overview**: Real-time statistics and recent cases
- **Cases View**: Browse all cases with filtering and status grouping
- **Case Details**: Detailed view with field progress, audit trail, and missing information
- **Audit Log**: Complete history of all actions and state changes
- **Real-time Data**: Direct Firestore integration for live updates

## Tech Stack

- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- Firebase Admin SDK
- Server-Side Rendering

## Setup

1. **Install dependencies**:
```bash
cd dashboard
npm install
```

2. **Configure environment**:
Create `.env.local`:
```bash
FIRESTORE_PROJECT_ID=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

3. **Run development server**:
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Build & Deploy

### Type Check
```bash
npm run type-check
```

### Production Build
```bash
npm run build
npm start
```

### Verify Build
```bash
# Ensure both pass with no errors:
tsc --noEmit
npm run build
```

## Project Structure

```
dashboard/
├── src/
│   ├── app/              # Next.js App Router pages
│   │   ├── page.tsx     # Dashboard home
│   │   ├── cases/       # Cases pages
│   │   ├── audit/       # Audit log page
│   │   └── layout.tsx   # Root layout
│   ├── components/       # Reusable React components
│   ├── lib/             # Utility functions & API
│   │   ├── firestore.ts # Firestore client
│   │   ├── api.ts       # Data fetching
│   │   └── utils.ts     # Helpers
│   └── types/           # TypeScript types
├── public/              # Static assets
└── package.json
```

## Pages

### Dashboard (`/`)
- Summary statistics
- Total cases, open, in progress, completed
- LoA-specific metrics
- Recent cases grid

### Cases List (`/cases`)
- All cases with status tabs
- Filterable by status
- Case cards with progress indicators
- Direct links to case details

### Case Detail (`/cases/[id]`)
- Complete case information
- Field progress tracking (for LoA cases)
- Received vs missing fields
- Full audit trail
- Case metadata and tags

### Audit Log (`/audit`)
- Chronological list of all actions
- Action type, timestamp, status
- Links to related cases
- Triggered by information

## Development

### Type Safety
All data fetching and components are fully typed with TypeScript.

### Data Fetching
Server Components fetch data directly from Firestore on each request.

### Styling
Tailwind CSS utility classes for responsive, professional design.

## Deployment

Deploy to Vercel, Railway, or any Node.js hosting:

```bash
npm run build
npm start
```

Ensure environment variables are set in production.

## Performance

- Server-side rendering for fast initial load
- Dynamic routes for case details
- Firestore queries optimized with indexes
- Responsive design for all devices
