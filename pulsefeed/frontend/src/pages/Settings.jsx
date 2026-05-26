import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Atom,
  BarChart2,
  BookOpen,
  Bot,
  Brain,
  Check,
  Cloud,
  Code2,
  FileText,
  HelpCircle,
  Link,
  Newspaper,
  Palette,
  Rss,
  Shield,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import TagInput from "../components/TagInput";
import { API_URL } from "../config";
import { settingsSchema, zodErrorsToMap } from "../lib/validation";

const FIELDS = [
  { id: "AI & Machine Learning", label: "AI & Machine Learning", icon: Brain },
  { id: "Software Engineering", label: "Software Engineering", icon: Code2 },
  { id: "Cybersecurity", label: "Cybersecurity", icon: Shield },
  { id: "Data Science", label: "Data Science", icon: BarChart2 },
  { id: "Cloud & DevOps", label: "Cloud & DevOps", icon: Cloud },
  { id: "Blockchain & Web3", label: "Blockchain & Web3", icon: Link },
  { id: "Product & Design", label: "Product & Design", icon: Palette },
  { id: "Quantum Computing", label: "Quantum Computing", icon: Atom },
  { id: "Robotics & Embedded", label: "Robotics & Embedded", icon: Bot },
  { id: "Other", label: "Other", icon: HelpCircle },
];

const SUB_FIELD_PLACEHOLDER = {
  "AI & Machine Learning":
    "e.g. LLMs, Computer Vision, Reinforcement Learning…",
  "Software Engineering": "e.g. Backend, Frontend, Mobile, APIs…",
  Cybersecurity: "e.g. Zero Trust, Penetration Testing, OSINT…",
  "Data Science": "e.g. NLP, Time Series, Data Visualisation…",
  "Cloud & DevOps": "e.g. Kubernetes, Terraform, CI/CD…",
  "Blockchain & Web3": "e.g. DeFi, Smart Contracts, Layer 2…",
  "Product & Design": "e.g. UX Research, Design Systems, Prototyping…",
  "Quantum Computing": "e.g. Quantum Algorithms, Error Correction, Qubits…",
  "Robotics & Embedded": "e.g. ROS, Microcontrollers, Sensor Fusion…",
  Other: "e.g. specific topics you're interested in…",
};

const FORMAT_CARDS = [
  {
    id: "Research Papers",
    label: "Research Papers",
    description: "ArXiv · DeepMind · OpenAI",
    icon: FileText,
  },
  {
    id: "Technical Articles",
    label: "Technical Articles",
    description: "Medium · Dev.to · Hashnode",
    icon: Newspaper,
  },
  {
    id: "Books & Guides",
    label: "Books & Guides",
    description: "O'Reilly · Manning · Roadmap.sh",
    icon: BookOpen,
  },
  {
    id: "Engineering Blogs",
    label: "Engineering Blogs",
    description: "Netflix · Uber · Meta Infra",
    icon: Rss,
  },
];

const MAX_NAME = 100;
const MAX_OCC = 150;

const TAXONOMY_TAGS = [
  {
    id: "AI Engineering",
    label: "AI Engineering",
    desc: "Inference, serving, quantization",
  },
  {
    id: "Agentic Workflows",
    label: "Agentic Workflows",
    desc: "LLM agents, tool use, planning",
  },
  { id: "LLMOps", label: "LLMOps", desc: "Monitoring, evals, fine-tuning" },
  {
    id: "Distributed Systems",
    label: "Distributed Systems",
    desc: "Consensus, Kafka, microservices",
  },
  {
    id: "Data Engineering",
    label: "Data Engineering",
    desc: "Pipelines, vector DBs, lakehouses",
  },
  {
    id: "Cybersecurity/Zero-Trust",
    label: "Cybersecurity",
    desc: "Zero-trust, eBPF, LLM security",
  },
  {
    id: "GPU Optimization",
    label: "GPU Optimization",
    desc: "CUDA, Flash Attention, mixed precision",
  },
  {
    id: "Edge Computing",
    label: "Edge Computing",
    desc: "Edge inference, TFLite, federated",
  },
  {
    id: "MLOps",
    label: "MLOps",
    desc: "CI/CD, model registry, drift detection",
  },
];

export default function Settings() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const userId = user?.id;

  const [name, setName] = useState("");
  const [occupation, setOccupation] = useState("");
  const [field, setField] = useState("");
  const [subFields, setSubFields] = useState([]);
  const [preferredFormats, setPreferredFormats] = useState([]);
  const [refreshInterval, setRefreshInterval] = useState(6);
  const [taxonomyTags, setTaxonomyTags] = useState([]);
  const [excludedTopics, setExcludedTopics] = useState([]);
  const [explorationMode, setExplorationMode] = useState("broad");
  const [errors, setErrors] = useState({});
  const [apiError, setApiError] = useState("");
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [fetching, setFetching] = useState(true);

  useEffect(() => {
    if (!userId) return;
    fetch(`${API_URL}/users/${userId}`, { credentials: "include" })
      .then((r) => r.json())
      .then((u) => {
        setName(u.name ?? "");
        setOccupation(u.occupation ?? "");
        setField(u.field ?? "");
        setSubFields(u.sub_fields ?? []);
        setPreferredFormats(u.preferred_formats ?? []);
        setRefreshInterval(u.refresh_interval_hours ?? 6);
        setTaxonomyTags(u.taxonomy_tags ?? []);
        setExcludedTopics(u.excluded_topics ?? []);
        setExplorationMode(u.exploration_mode ?? "broad");
      })
      .catch(() => setApiError("Could not load your profile."))
      .finally(() => setFetching(false));
  }, [userId]);

  function validate() {
    const result = settingsSchema.safeParse({
      name,
      occupation,
      field,
      sub_fields: subFields,
      preferred_formats: preferredFormats,
      refresh_interval_hours: refreshInterval,
      taxonomy_tags: taxonomyTags,
      excluded_topics: excludedTopics,
      exploration_mode: explorationMode,
    });
    return result.success ? {} : zodErrorsToMap(result.error.issues);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const e2 = validate();
    if (Object.keys(e2).length) {
      setErrors(e2);
      return;
    }
    setErrors({});
    setApiError("");
    setSaved(false);
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/users/${userId}`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          occupation: occupation.trim(),
          field,
          sub_fields: subFields,
          preferred_formats: preferredFormats,
          refresh_interval_hours: refreshInterval,
          taxonomy_tags: taxonomyTags,
          excluded_topics: excludedTopics,
          exploration_mode: explorationMode,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Error ${res.status}`);
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setApiError(err.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  if (fetching) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto px-4 sm:px-6 py-8">
      <h2 className="text-xl font-bold text-white mb-1">Settings</h2>
      <p className="text-sm text-slate-400 mb-8">
        Update your profile to re-tune your feed.
      </p>

      <form onSubmit={handleSubmit} noValidate className="space-y-6">
        {apiError && (
          <div className="flex items-start gap-3 bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3">
            <svg
              className="w-5 h-5 text-red-400 shrink-0 mt-0.5"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
              />
            </svg>
            <p className="text-sm text-red-300">{apiError}</p>
          </div>
        )}

        {saved && (
          <div className="flex items-center gap-2 bg-violet-500/10 border border-violet-500/30 rounded-lg px-4 py-3">
            <svg
              className="w-4 h-4 text-violet-400"
              fill="none"
              stroke="currentColor"
              strokeWidth={2.5}
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M5 13l4 4L19 7"
              />
            </svg>
            <p className="text-sm text-violet-300">
              Profile saved successfully.
            </p>
          </div>
        )}

        {/* Name */}
        <div>
          <div className="flex justify-between mb-1.5">
            <label className="text-sm font-medium text-slate-200">Name</label>
            <span
              className={`text-xs ${name.length > MAX_NAME * 0.9 ? "text-amber-400" : "text-slate-500"}`}
            >
              {name.length}/{MAX_NAME}
            </span>
          </div>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value.slice(0, MAX_NAME))}
            className={`w-full px-3.5 py-2.5 bg-slate-800 border rounded-lg text-sm text-slate-200 placeholder-slate-500 outline-none transition-colors ${
              errors.name
                ? "border-red-500"
                : "border-slate-700 focus:border-violet-500 focus:ring-1 focus:ring-violet-500/30"
            }`}
          />
          {errors.name && (
            <p className="mt-1.5 text-xs text-red-400">{errors.name}</p>
          )}
        </div>

        {/* Occupation */}
        <div>
          <div className="flex justify-between mb-1.5">
            <label className="text-sm font-medium text-slate-200">
              Job Title / Role
            </label>
            <span
              className={`text-xs ${occupation.length > MAX_OCC * 0.9 ? "text-amber-400" : "text-slate-500"}`}
            >
              {occupation.length}/{MAX_OCC}
            </span>
          </div>
          <input
            type="text"
            value={occupation}
            onChange={(e) => setOccupation(e.target.value.slice(0, MAX_OCC))}
            className={`w-full px-3.5 py-2.5 bg-slate-800 border rounded-lg text-sm text-slate-200 placeholder-slate-500 outline-none transition-colors ${
              errors.occupation
                ? "border-red-500"
                : "border-slate-700 focus:border-violet-500 focus:ring-1 focus:ring-violet-500/30"
            }`}
          />
          {errors.occupation && (
            <p className="mt-1.5 text-xs text-red-400">{errors.occupation}</p>
          )}
        </div>

        {/* Primary Field */}
        <div>
          <label className="block text-sm font-medium text-slate-200 mb-1.5">
            Primary Field
          </label>
          <div className="flex flex-wrap gap-2">
            {FIELDS.map((f) => {
              const Icon = f.icon;
              const selected = field === f.id;
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => {
                    setField(f.id);
                    setErrors((prev) => ({ ...prev, field: undefined }));
                  }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                    selected
                      ? "border-violet-500 bg-violet-500/10 text-violet-300 ring-1 ring-violet-500/30"
                      : "border-slate-700 bg-slate-800/50 text-slate-400 hover:border-slate-500 hover:text-slate-300"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {f.label}
                </button>
              );
            })}
          </div>
          {errors.field && (
            <p className="mt-2 text-xs text-red-400">{errors.field}</p>
          )}
        </div>

        {/* Sub-fields */}
        <div>
          <label className="block text-sm font-medium text-slate-200 mb-1.5">
            Areas of Focus
          </label>
          <TagInput
            tags={subFields}
            onChange={setSubFields}
            placeholder={
              SUB_FIELD_PLACEHOLDER[field] ??
              "e.g. specific topics… press Enter"
            }
          />
          {errors.subFields && (
            <p className="mt-1.5 text-xs text-red-400">{errors.subFields}</p>
          )}
        </div>

        {/* Media Formats */}
        <div>
          <label className="block text-sm font-medium text-slate-200 mb-1">
            Preferred Formats{" "}
            <span className="text-slate-500 font-normal">(optional)</span>
          </label>
          <p className="text-xs text-slate-500 mb-3">
            Your feed will prioritise content from these sources.
          </p>
          <div className="grid grid-cols-2 gap-2">
            {FORMAT_CARDS.map((card) => {
              const Icon = card.icon;
              const selected = preferredFormats.includes(card.id);
              return (
                <button
                  key={card.id}
                  type="button"
                  onClick={() =>
                    setPreferredFormats((prev) =>
                      prev.includes(card.id)
                        ? prev.filter((f) => f !== card.id)
                        : [...prev, card.id],
                    )
                  }
                  className={`relative flex items-center gap-3 p-3 rounded-lg border text-left transition-all ${
                    selected
                      ? "border-violet-500 ring-2 ring-violet-500/20 bg-violet-500/5"
                      : "border-slate-700 bg-slate-800/50 hover:border-slate-600"
                  }`}
                >
                  {selected && (
                    <div className="absolute top-2 right-2 w-4 h-4 bg-violet-500 rounded-full flex items-center justify-center">
                      <Check
                        className="w-2.5 h-2.5 text-white"
                        strokeWidth={3}
                      />
                    </div>
                  )}
                  <Icon
                    className={`w-5 h-5 shrink-0 ${selected ? "text-violet-400" : "text-slate-400"}`}
                  />
                  <div>
                    <p
                      className={`text-xs font-semibold ${selected ? "text-violet-300" : "text-slate-300"}`}
                    >
                      {card.label}
                    </p>
                    <p className="text-[10px] text-slate-500">
                      {card.description}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Topic Focus */}
        <div>
          <label className="block text-sm font-medium text-slate-200 mb-1">
            Topic Focus{" "}
            <span className="text-slate-500 font-normal">(optional)</span>
          </label>
          <p className="text-xs text-slate-500 mb-3">
            Select topics to prioritise. Leave empty to receive all topics.
          </p>
          <div className="grid grid-cols-1 gap-2">
            {TAXONOMY_TAGS.map((tag) => {
              const selected = taxonomyTags.includes(tag.id);
              return (
                <button
                  key={tag.id}
                  type="button"
                  onClick={() =>
                    setTaxonomyTags((prev) =>
                      prev.includes(tag.id)
                        ? prev.filter((t) => t !== tag.id)
                        : [...prev, tag.id],
                    )
                  }
                  className={`relative flex items-center justify-between p-3 rounded-lg border text-left transition-all ${
                    selected
                      ? "border-violet-500 ring-1 ring-violet-500/20 bg-violet-500/5"
                      : "border-slate-700 bg-slate-800/50 hover:border-slate-600"
                  }`}
                >
                  <div>
                    <p
                      className={`text-xs font-semibold ${selected ? "text-violet-300" : "text-slate-300"}`}
                    >
                      {tag.label}
                    </p>
                    <p className="text-[10px] text-slate-500 mt-0.5">
                      {tag.desc}
                    </p>
                  </div>
                  {selected && (
                    <div className="w-4 h-4 bg-violet-500 rounded-full flex items-center justify-center shrink-0">
                      <Check
                        className="w-2.5 h-2.5 text-white"
                        strokeWidth={3}
                      />
                    </div>
                  )}
                </button>
              );
            })}
          </div>
          {taxonomyTags.length > 0 && (
            <button
              type="button"
              onClick={() => setTaxonomyTags([])}
              className="mt-2 text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              Clear selection (receive all topics)
            </button>
          )}
        </div>

        {/* Exploration Mode */}
        {taxonomyTags.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-slate-200 mb-1">
              Exploration Mode
            </label>
            <p className="text-xs text-slate-500 mb-3">
              Controls how strictly your feed filters by selected topics.
            </p>
            <div className="flex gap-2">
              {[
                {
                  id: "narrow",
                  label: "Narrow",
                  hint: "Only your selected topics",
                },
                {
                  id: "broad",
                  label: "Broad",
                  hint: "Selected topics + adjacent content",
                },
              ].map((mode) => (
                <button
                  key={mode.id}
                  type="button"
                  onClick={() => setExplorationMode(mode.id)}
                  className={`flex-1 py-2.5 px-3 rounded-lg border text-sm font-semibold transition-all ${
                    explorationMode === mode.id
                      ? "border-violet-500 bg-violet-500/10 text-violet-300 ring-1 ring-violet-500/30"
                      : "border-slate-700 bg-slate-800/50 text-slate-400 hover:border-slate-500 hover:text-slate-300"
                  }`}
                >
                  {mode.label}
                  <p className="text-[10px] font-normal mt-0.5 opacity-70">
                    {mode.hint}
                  </p>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Excluded Topics */}
        <div>
          <label className="block text-sm font-medium text-slate-200 mb-1">
            Exclude Topics{" "}
            <span className="text-slate-500 font-normal">(optional)</span>
          </label>
          <p className="text-xs text-slate-500 mb-3">
            Keywords to block from your feed. Press Enter to add.
          </p>
          <TagInput
            tags={excludedTopics}
            onChange={setExcludedTopics}
            placeholder="e.g. blockchain, web3, tutorials…"
          />
        </div>

        {/* Feed Refresh Interval */}
        <div>
          <label className="block text-sm font-medium text-slate-200 mb-1">
            Feed Refresh Interval
          </label>
          <p className="text-xs text-slate-500 mb-3">
            How often your feed pulls fresh content from the pipeline.
          </p>
          <div className="flex gap-2">
            {[3, 6, 12].map((hrs) => (
              <button
                key={hrs}
                type="button"
                onClick={() => setRefreshInterval(hrs)}
                className={`flex-1 py-2 rounded-lg border text-sm font-semibold transition-all ${
                  refreshInterval === hrs
                    ? "border-violet-500 bg-violet-500/10 text-violet-300 ring-1 ring-violet-500/30"
                    : "border-slate-700 bg-slate-800/50 text-slate-400 hover:border-slate-500 hover:text-slate-300"
                }`}
              >
                Every {hrs}h
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-xs text-slate-500">
            {refreshInterval === 3
              ? "High frequency — best for fast-moving fields"
              : refreshInterval === 6
                ? "Standard — balanced freshness and efficiency"
                : "Low frequency — ideal for stable, long-form fields"}
          </p>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={loading}
            className="flex-1 py-2.5 bg-violet-600 hover:bg-violet-500 disabled:bg-violet-800 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <svg
                  className="animate-spin w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                Saving…
              </>
            ) : (
              "Save Changes"
            )}
          </button>
          <button
            type="button"
            onClick={handleLogout}
            className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-sm font-medium rounded-lg transition-colors"
          >
            Sign out
          </button>
        </div>
      </form>
    </div>
  );
}
