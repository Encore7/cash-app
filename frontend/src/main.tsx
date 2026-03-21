import React, { useMemo } from 'react'
import { createRoot } from 'react-dom/client'
import {
  createBrowserRouter,
  RouterProvider,
  Outlet,
  useNavigate,
  useLocation,
  Navigate,
} from 'react-router-dom'
import { AppProvider } from '@toolpad/core/AppProvider'
import { DashboardLayout } from '@toolpad/core/DashboardLayout'
import WorkHistoryIcon from '@mui/icons-material/WorkHistory'
import DashboardIcon from '@mui/icons-material/Dashboard'
import BarChartIcon from '@mui/icons-material/BarChart'
import MenuBookIcon from '@mui/icons-material/MenuBook'
import JobsPage from './pages/JobsPage'
import DashboardPage from './pages/DashboardPage'
import AnalyticsPage from './pages/AnalyticsPage'
import JournalPage from './pages/JournalPage'

const NAVIGATION = [
  {
    segment: 'jobs',
    title: 'Jobs',
    icon: <WorkHistoryIcon />,
  },
  {
    segment: 'analytics',
    title: 'Analytics',
    icon: <BarChartIcon />,
  },
  {
    segment: 'journal',
    title: 'Journal Entries',
    icon: <MenuBookIcon />,
  },
  {
    segment: 'dashboard',
    title: 'Dashboard',
    icon: <DashboardIcon />,
  },
]

const BRANDING = {
  title: 'Cash Application',
}

function AppShell() {
  const navigate = useNavigate()
  const location = useLocation()

  const router = useMemo(
    () => ({
      pathname: location.pathname,
      searchParams: new URLSearchParams(location.search),
      navigate: (path) => navigate(String(path)),
    }),
    [navigate, location],
  )

  return (
    <AppProvider navigation={NAVIGATION} router={router} branding={BRANDING}>
      <DashboardLayout>
        <Outlet />
      </DashboardLayout>
    </AppProvider>
  )
}

const browserRouter = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/jobs" replace /> },
      { path: 'jobs', element: <JobsPage /> },
      { path: 'analytics', element: <AnalyticsPage /> },
      { path: 'journal', element: <JournalPage /> },
      { path: 'dashboard', element: <DashboardPage /> },
    ],
  },
])

createRoot(document.getElementById('root')).render(
  <RouterProvider router={browserRouter} />,
)
