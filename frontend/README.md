# KNEXUS Frontend

The web application lives in `frontend/app` (Vite + React 19 + TypeScript).
To run the frontend: `cd frontend/app && npm ci && npm run dev`.
Supported modes via `VITE_DATA_MODE`: `mock` (client-side mock data) or `live` (calls backend).
The browser calls only the KNEXUS backend at `http://localhost:8000/api/v1`, never external model providers directly, and holds no keys.
For complete architectural details and component documentation, see `frontend/docs/README.md` once Zaid's PR #25 lands.
