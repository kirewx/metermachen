import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { isUnauthorized } from './api/client'
import { ToastProvider } from './components/ui/Toast'
import './index.css'

// Läuft die Session irgendwann ab (Server-Neustart, 30 Tage um, Account
// deaktiviert), antwortet jede geschützte Anfrage mit 401. Global abfangen und
// `me` auf null setzen → App rendert den Login statt roter Fehlerzeilen.
function handleAuthError(error: unknown) {
  if (isUnauthorized(error)) {
    queryClient.setQueryData(['me'], null)
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Bei 401 nicht wiederholen (Session ist weg), sonst einmal (Netz-Aussetzer).
      retry: (failureCount, error) => !isUnauthorized(error) && failureCount < 1,
    },
  },
  queryCache: new QueryCache({ onError: handleAuthError }),
  mutationCache: new MutationCache({ onError: handleAuthError }),
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ToastProvider>
          <App />
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
