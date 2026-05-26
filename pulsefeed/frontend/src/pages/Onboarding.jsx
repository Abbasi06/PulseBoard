import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import InterestPicker from "../components/InterestPicker";
import { MIN_SUBFIELDS } from "../constants/taxonomy";
import { API_URL } from "../config";
import {
  onboardingStep1Schema,
  onboardingStep2Schema,
  zodErrorsToMap,
} from "../lib/validation";

const MAX_NAME = 100;
const MAX_OCC = 150;

// ---------------------------------------------------------------------------
// Step indicator
// ---------------------------------------------------------------------------

const STEP_LABELS = ["Identity", "Expertise"];

function StepIndicator({ current }) {
  return (
    <div className="flex items-center gap-0 mb-10 border-b-2 border-ink pb-6">
      {STEP_LABELS.map((label, i) => {
        const n = i + 1;
        const done = n < current;
        const active = n === current;
        return (
          <div key={label} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center gap-2">
              <div
                className={`w-10 h-10 border-2 items-center justify-center text-sm font-bold font-mono transition-all duration-300 interactive-snap ${
                  done
                    ? "bg-ink border-ink text-paper flex"
                    : active
                      ? "bg-clay border-clay text-paper flex"
                      : "bg-paper border-ink text-ink flex"
                }`}
              >
                {done ? (
                  <Check className="w-5 h-5 text-paper" strokeWidth={3} />
                ) : (
                  n
                )}
              </div>
              <span
                className={`text-[10px] font-mono tracking-widest uppercase font-bold ${
                  active ? "text-clay" : "text-ink"
                }`}
              >
                {label}
              </span>
            </div>
            {i < STEP_LABELS.length - 1 && (
              <div className="flex-1 h-[2px] mx-4 bg-ink" />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function Onboarding() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [occupation, setOccupation] = useState("");
  const [field, setField] = useState("");
  const [subFields, setSubFields] = useState([]);
  const [refreshInterval, setRefreshInterval] = useState(6);
  const [errors, setErrors] = useState({});
  const [apiError, setApiError] = useState("");
  const [loading, setLoading] = useState(false);

  function validateStep1() {
    const result = onboardingStep1Schema.safeParse({
      name,
      occupation,
      refresh_interval_hours: refreshInterval,
    });
    return result.success ? {} : zodErrorsToMap(result.error.issues);
  }

  function validateStep2() {
    const result = onboardingStep2Schema.safeParse({
      field,
      sub_fields: subFields,
    });
    return result.success ? {} : zodErrorsToMap(result.error.issues);
  }

  function handleNext() {
    const e = validateStep1();
    if (Object.keys(e).length) {
      setErrors(e);
      return;
    }
    setErrors({});
    setStep(2);
  }

  function handleBack() {
    setErrors({});
    setStep(1);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const e2 = validateStep2();
    if (Object.keys(e2).length) {
      setErrors(e2);
      setStep(2);
      return;
    }
    setErrors({});
    setApiError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/users`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          occupation: occupation.trim(),
          selected_chips: subFields.slice(0, 5),
          field,
          sub_fields: subFields,
          refresh_interval_hours: refreshInterval,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Error ${res.status}`);
      }
      const user = await res.json();
      login(user);
      navigate("/dashboard");
    } catch (err) {
      setApiError(err.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const canSubmit = field && subFields.length >= MIN_SUBFIELDS && !loading;

  return (
    // ── Outer shell ──────────────────────────────────────────────────────────
    // No background color here — the WarpBackground canvas (mounted in App.jsx)
    // provides the paper + particle layer beneath this component.
    // relative z-10 ensures this content stack sits above the fixed canvas (z-0).
    <div className="relative z-10 min-h-screen flex flex-col items-center justify-center px-4 py-12 font-sans selection:bg-clay selection:text-paper text-ink">
      <div className="w-full max-w-2xl">
        {/* ── Brand header ─────────────────────────────────────────────────────
            Floats directly on the canvas background (which is paper-colored),
            so no extra background needed here.                                */}
        <div className="text-center mb-8 border-b-2 border-ink pb-6">
          <h1 className="text-5xl font-display font-bold tracking-tighter uppercase">
            Pulse <br /> Feed
          </h1>
          <p className="mt-4 font-mono text-xs uppercase tracking-widest text-ink">
            [/] Initialize Your Architecture — Step {step} of 2
          </p>
        </div>

        {/* ── Form card ────────────────────────────────────────────────────────
            bg-paper/95 + backdrop-blur-sm: frosted-glass treatment —
            the particle network is faintly visible through the card edges
            while the form content stays fully legible.                        */}
        <div className="relative bg-paper/95 backdrop-blur-sm border-2 border-ink p-8 md:p-12">
          {/* Corner tag */}
          <div className="absolute top-0 right-0 bg-clay text-paper px-2 py-1 text-[10px] font-mono font-bold uppercase tracking-widest border-l border-b border-ink">
            [!] FORM 001
          </div>

          <StepIndicator current={step} />

          {/* API error banner */}
          {apiError && (
            <div className="flex items-start gap-3 border-2 border-ink bg-[#FFECEC] px-4 py-3 mb-8">
              <span className="text-xl shrink-0 mt-0.5" aria-hidden="true">
                ⚠️
              </span>
              <p className="text-sm font-mono font-bold uppercase text-ink">
                {apiError}
              </p>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            {/* ── Step 1: Identity ── */}
            {step === 1 && (
              <div className="space-y-8">
                {/* Name */}
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-xs font-mono font-bold uppercase tracking-widest text-ink">
                      Subject Alias [Name]
                    </label>
                    <span
                      className={`text-[10px] font-mono font-bold ${name.length > MAX_NAME * 0.9 ? "text-red-500" : "text-ink"}`}
                    >
                      {name.length}/{MAX_NAME}
                    </span>
                  </div>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value.slice(0, MAX_NAME))}
                    placeholder="E.G. ADA LOVELACE"
                    className={`w-full px-4 py-3 bg-paper border-2 text-sm font-mono text-ink placeholder-steel outline-none focus:border-clay focus:shadow-[4px_4px_0px_#D97757] ${
                      errors.name ? "border-red-500" : "border-ink"
                    }`}
                  />
                  {errors.name && (
                    <p className="mt-2 text-[10px] font-mono font-bold uppercase text-red-500 tracking-widest">
                      {errors.name}
                    </p>
                  )}
                </div>

                {/* Occupation */}
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-xs font-mono font-bold uppercase tracking-widest text-ink">
                      Designation [Role]
                    </label>
                    <span
                      className={`text-[10px] font-mono font-bold ${occupation.length > MAX_OCC * 0.9 ? "text-red-500" : "text-ink"}`}
                    >
                      {occupation.length}/{MAX_OCC}
                    </span>
                  </div>
                  <input
                    type="text"
                    value={occupation}
                    onChange={(e) =>
                      setOccupation(e.target.value.slice(0, MAX_OCC))
                    }
                    placeholder="E.G. CHIEF SYSTEMS ARCHITECT"
                    className={`w-full px-4 py-3 bg-paper border-2 text-sm font-mono text-ink placeholder-steel outline-none focus:border-clay focus:shadow-[4px_4px_0px_#D97757] ${
                      errors.occupation ? "border-red-500" : "border-ink"
                    }`}
                  />
                  {errors.occupation && (
                    <p className="mt-2 text-[10px] font-mono font-bold uppercase text-red-500 tracking-widest">
                      {errors.occupation}
                    </p>
                  )}
                </div>

                {/* Refresh cadence */}
                <div>
                  <label className="text-xs font-mono font-bold uppercase tracking-widest text-ink mb-3 block">
                    Feed Refresh Cadence
                  </label>
                  <p className="text-[10px] font-mono text-steel uppercase tracking-widest mb-3">
                    How often should your feed pull fresh content?
                  </p>
                  <div className="flex gap-3">
                    {[3, 6, 12].map((hrs) => (
                      <button
                        key={hrs}
                        type="button"
                        onClick={() => setRefreshInterval(hrs)}
                        className={`flex-1 py-3 border-2 text-sm font-mono font-bold uppercase tracking-widest transition-all interactive-snap ${
                          refreshInterval === hrs
                            ? "bg-ink border-ink text-paper"
                            : "bg-paper border-ink text-ink hover:bg-ink hover:text-paper"
                        }`}
                      >
                        Every {hrs}h
                      </button>
                    ))}
                  </div>
                  <p className="mt-2 text-[10px] font-mono text-steel uppercase tracking-widest">
                    {refreshInterval === 3
                      ? "[3H] HIGH FREQUENCY — ideal for fast-moving fields"
                      : refreshInterval === 6
                        ? "[6H] STANDARD — balanced freshness and efficiency"
                        : "[12H] LOW FREQUENCY — ideal for stable, long-form fields"}
                  </p>
                </div>

                <div className="pt-4 border-t-2 border-ink">
                  <button
                    type="button"
                    onClick={handleNext}
                    className="w-full py-4 btn-print hover:shadow-[4px_4px_0_var(--color-ink)]"
                  >
                    PROCEED: EXPERTISE →
                  </button>
                </div>
              </div>
            )}

            {/* ── Step 2: Expertise ── */}
            {step === 2 && (
              <div className="space-y-8">
                <InterestPicker
                  field={field}
                  subFields={subFields}
                  onFieldChange={(f) => {
                    setField(f);
                    setErrors((prev) => ({
                      ...prev,
                      field: undefined,
                      subFields: undefined,
                    }));
                  }}
                  onSubFieldsChange={(sf) => {
                    setSubFields(sf);
                    setErrors((prev) => ({ ...prev, subFields: undefined }));
                  }}
                />

                {(errors.field || errors.subFields) && (
                  <p className="text-[10px] font-mono font-bold uppercase text-red-500 tracking-widest text-center">
                    {errors.field || errors.subFields}
                  </p>
                )}

                <div className="flex flex-col sm:flex-row gap-4 pt-6 border-t-2 border-ink">
                  <button
                    type="button"
                    onClick={handleBack}
                    className="px-6 py-4 bg-paper border-2 border-ink text-ink font-mono font-bold text-sm tracking-widest uppercase hover:bg-ink hover:text-paper interactive-snap"
                  >
                    ← BACK
                  </button>
                  <button
                    type="submit"
                    disabled={!canSubmit}
                    className="flex-1 py-4 px-6 btn-print hover:shadow-[4px_4px_0_var(--color-ink)] disabled:shadow-none flex items-center justify-center gap-2"
                  >
                    {loading
                      ? "INITIALIZING SWARM..."
                      : "COMMENCE FEED GENERATION →"}
                  </button>
                </div>
              </div>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
