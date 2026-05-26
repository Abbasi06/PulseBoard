/**
 * Zod schemas that mirror the backend Pydantic validators exactly.
 * Used in Onboarding and Settings to give early, typed feedback before
 * the request reaches the API.
 *
 * Limits are intentionally identical to schemas.py:
 *   name           max 100 chars
 *   occupation     max 150 chars
 *   sub_fields     1–10 items, each max 100 chars
 *   excluded_topics max 20 items, each max 50 chars
 *   preferred_formats max 4 items
 *   refresh_interval_hours enum [3, 6]
 *   exploration_mode enum ["narrow", "broad"]
 */
import { z } from "zod";
import { MIN_SUBFIELDS } from "../constants/taxonomy";

export const onboardingStep1Schema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Name is required")
    .max(100, "Name must be 100 characters or fewer"),
  occupation: z
    .string()
    .trim()
    .min(1, "Occupation is required")
    .max(150, "Occupation must be 150 characters or fewer"),
  refresh_interval_hours: z.union([z.literal(3), z.literal(6), z.literal(12)]),
});

export const onboardingStep2Schema = z.object({
  field: z.string().min(1, "Select a domain first"),
  sub_fields: z
    .array(z.string().trim().min(1).max(100))
    .min(MIN_SUBFIELDS, `Select at least ${MIN_SUBFIELDS} focus areas`)
    .max(10, "Maximum 10 focus areas"),
});

export const settingsSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Name is required")
    .max(100, "Name must be 100 characters or fewer"),
  occupation: z
    .string()
    .trim()
    .min(1, "Occupation is required")
    .max(150, "Occupation must be 150 characters or fewer"),
  field: z.string().min(1, "Select your primary field"),
  sub_fields: z
    .array(z.string().trim().min(1).max(100))
    .min(1, "Add at least one area of focus")
    .max(10, "Maximum 10 focus areas"),
  preferred_formats: z.array(z.string()).max(4),
  refresh_interval_hours: z.union([z.literal(3), z.literal(6), z.literal(12)]),
  taxonomy_tags: z.array(z.string()),
  excluded_topics: z
    .array(
      z
        .string()
        .trim()
        .max(50, "Each excluded topic must be 50 characters or fewer"),
    )
    .max(20, "Maximum 20 excluded topics"),
  exploration_mode: z.enum(["narrow", "broad"]),
});

/**
 * Convert a Zod error's issues to a flat { fieldName: message } map.
 * Handles array-field errors (path[0] is the field key) and remaps
 * snake_case keys to the camelCase names used in component state.
 */
export function zodErrorsToMap(issues) {
  const keyMap = { sub_fields: "subFields" };
  const errs = {};
  for (const issue of issues) {
    if (issue.path.length === 0) continue;
    const raw = String(issue.path[0]);
    const key = keyMap[raw] ?? raw;
    if (!errs[key]) errs[key] = issue.message;
  }
  return errs;
}
