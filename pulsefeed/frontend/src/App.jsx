import { Component } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import DashboardLayout from "./components/DashboardLayout";
import { lazy, Suspense } from "react";
import LandingPage from "./pages/LandingPage";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Onboarding = lazy(() => import("./pages/Onboarding"));
const Settings = lazy(() => import("./pages/Settings"));
import WarpBackground from "./components/WarpBackground";

// ---------------------------------------------------------------------------
// Error boundary — prevents white-screen crashes
// ---------------------------------------------------------------------------

class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
          <div className="max-w-sm text-center space-y-5">
            <div className="w-14 h-14 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto">
              <svg
                className="w-7 h-7 text-red-400"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.8}
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
                />
              </svg>
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-100 mb-1">
                Something went wrong
              </h2>
              <p className="text-xs text-slate-500">
                {this.state.error?.message || "Unexpected error"}
              </p>
            </div>
            <button
              onClick={() => window.location.reload()}
              className="btn-primary px-5 py-2 rounded-xl text-sm"
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// ---------------------------------------------------------------------------
// Page transition variants
// ---------------------------------------------------------------------------

const fade = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.35, ease: "easeOut" } },
  exit: { opacity: 0, transition: { duration: 0.2 } },
};

// Landing exits sliding left, onboarding enters from right — simultaneous pan effect
const landingExit = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.4, ease: "easeOut" } },
  exit: {
    opacity: 0,
    x: -60,
    transition: { duration: 0.45, ease: [0.4, 0, 0.2, 1] },
  },
};

const slideFromRight = {
  initial: { opacity: 0, x: 60 },
  animate: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] },
  },
  exit: { opacity: 0, x: -40, transition: { duration: 0.3 } },
};

function Page({ children, variant = fade }) {
  return (
    <motion.div
      variants={variant}
      initial="initial"
      animate="animate"
      exit="exit"
      style={{ minHeight: "100vh" }}
    >
      {children}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Loading screen shown while AuthContext checks the cookie
// ---------------------------------------------------------------------------

function Pulse() {
  return (
    <div className="min-h-screen bg-neutral-950 flex items-center justify-center">
      <div className="flex gap-1.5">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="w-2 h-2 rounded-full bg-violet-500"
            animate={{ scale: [1, 1.6, 1], opacity: [0.5, 1, 0.5] }}
            transition={{ repeat: Infinity, duration: 0.9, delay: i * 0.18 }}
          />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Protected route: waits for auth check before deciding
// ---------------------------------------------------------------------------

function ProtectedRoute({ children }) {
  const { isAuthenticated, checking } = useAuth();
  if (checking) return <Pulse />;
  return isAuthenticated ? children : <Navigate to="/" replace />;
}

// ---------------------------------------------------------------------------
// Routes tree (inside AuthProvider + BrowserRouter)
// ---------------------------------------------------------------------------

function AppRoutes() {
  const location = useLocation();
  const isOnboarding = location.pathname === "/onboarding";

  return (
    <>
      {/* Particle network — onboarding only; landing uses a clean paper background */}
      {isOnboarding && <WarpBackground />}

      <Suspense fallback={<Pulse />}>
        <AnimatePresence mode="sync" initial={false}>
          <Routes location={location} key={location.pathname}>
            <Route
              path="/"
              element={
                <Page variant={landingExit}>
                  <LandingPage />
                </Page>
              }
            />
            <Route
              path="/onboarding"
              element={
                <Page variant={slideFromRight}>
                  <Onboarding />
                </Page>
              }
            />
            <Route
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route
                path="/dashboard"
                element={
                  <Page variant={fade}>
                    <Dashboard />
                  </Page>
                }
              />
              <Route
                path="/settings"
                element={
                  <Page variant={fade}>
                    <Settings />
                  </Page>
                }
              />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AnimatePresence>
      </Suspense>
    </>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </ErrorBoundary>
  );
}
