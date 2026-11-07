# KNEXUS Frontend Documentation

## Running the Application

### Development Mode
```bash
npm run dev
```
Starts the Vite development server at `http://localhost:5173`.

### Mock Mode (Default)
The application defaults to mock mode, which serves responses from local JSON fixtures
under `src/mocks/data/`. No network access is required.

```bash
# VITE_DATA_MODE defaults to "mock"
VITE_DATA_MODE=mock
```

### Live Mode
To run against the real backend, set the environment variable to `live`:

```bash
VITE_DATA_MODE=live
```

```bash
npm run dev
```

### Running Tests
```bash
# Mock mode (default, jsdom)
npm run test

# Live mode (requires backend)
VITE_DATA_MODE=live npm run test
```

### Build
```bash
npm run build
```

## Mock vs Live Mode

- **`mock`**: Serves data from local JSON fixtures. No backend required.
  - Configured via `VITE_DATA_MODE=mock` (default)
  - Mock delay can be set via `VITE_MOCK_DELAY_MS`
  - Useful for development without a backend

- **`live`**: Queries the real KNEXUS backend API.
  - Configured via `VITE_DATA_MODE=live`
  - Requires backend server running at `VITE_API_BASE_URL`
  - Tests all API contracts and error handling

The active mode is always displayed in the UI header.
