import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "../context/AuthContext";

function getInitials(name) {
  return (name || "")
    .trim()
    .split(/\s+/)
    .map((w) => w[0]?.toUpperCase() || "")
    .slice(0, 2)
    .join("");
}

export default function DashboardLayout() {
  const navigate = useNavigate();
  const { logout, user } = useAuth();
  const initials = getInitials(user?.name);
  const [open, setOpen] = useState(false);

  async function handleLogout() {
    setOpen(false);
    await logout();
    navigate("/");
  }

  return (
    <div className="h-screen flex flex-col bg-space-black">
      {/* ── Mobile top bar ── */}
      <div className="md:hidden fixed top-0 inset-x-0 z-30 bg-space-black/90 backdrop-blur-md border-b border-deep-purple/30 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-full flex items-center justify-center text-white text-[10px] font-bold shrink-0 bg-gradient-to-br from-neon-pink to-steel-blue">
            {initials || "?"}
          </div>
          <span className="text-base font-bold text-text-primary">
            Pulse<span className="text-deep-purple">Feed</span>
          </span>
        </div>
        <nav className="flex gap-1">
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `p-2 rounded-lg transition-colors ${isActive ? "text-neon-cyan" : "text-text-secondary hover:text-text-primary"}`
            }
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.8}
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </NavLink>
          <button
            onClick={handleLogout}
            className="p-2 rounded-lg text-text-secondary hover:text-neon-pink transition-colors"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.8}
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
              />
            </svg>
          </button>
        </nav>
      </div>

      {/* ── Main content ── */}
      <main className="flex-1 min-h-0 md:pt-0 pt-14 overflow-hidden flex flex-col">
        <Outlet />
      </main>

      {/* ── Floating brand — desktop only ── */}
      <div
        className="hidden md:block fixed bottom-11 left-5 z-50"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
      >
        {/* Brand pill */}
        <motion.div
          whileHover={{ scale: 1.04 }}
          transition={{ type: "spring", stiffness: 400, damping: 25 }}
          className="flex items-center gap-3 px-4 py-2.5 cursor-pointer select-none liquid-glass shadow-none border-deep-purple/40"
        >
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0 bg-gradient-to-br from-neon-pink to-steel-blue"
            style={{
              boxShadow: "0 0 12px var(--color-neon-pink)",
            }}
          >
            {initials || "AI"}
          </div>
          <div className="leading-tight">
            <p className="text-sm font-bold text-text-primary">
              Pulse<span className="text-deep-purple">Feed</span>
            </p>
            <p className="text-[10px] text-text-secondary">AI knowledge feed</p>
          </div>
          <motion.svg
            animate={{ rotate: open ? 180 : 0 }}
            transition={{ duration: 0.2 }}
            className="w-3.5 h-3.5 text-slate-600 shrink-0 ml-0.5"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M19 9l-7 7-7-7"
            />
          </motion.svg>
        </motion.div>

        {/* Popup menu — opens upward */}
        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, y: 8, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.95 }}
              transition={{ type: "spring", stiffness: 440, damping: 30 }}
              className="absolute bottom-full left-0 mb-2 w-44 liquid-glass !rounded-2xl border-deep-purple/50 bg-space-black/80"
            >
              <NavLink
                to="/settings"
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 px-3.5 py-2.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "text-neon-cyan bg-neon-cyan/10"
                      : "text-text-secondary hover:text-text-primary hover:bg-white/5"
                  }`
                }
              >
                <svg
                  className="w-4 h-4 shrink-0"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.8}
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                Settings
              </NavLink>
              <div className="h-px mx-3 bg-deep-purple/20" />
              <button
                onClick={handleLogout}
                className="flex items-center gap-2.5 w-full px-3.5 py-2.5 text-sm font-medium text-text-secondary hover:text-neon-pink hover:bg-neon-pink/10 transition-colors"
              >
                <svg
                  className="w-4 h-4 shrink-0"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.8}
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                  />
                </svg>
                Sign out
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
