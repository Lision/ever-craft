# Nutrition MiniApp Generation

Use this reference after Figma MCP connectivity is verified and a mobile frame has been read with metadata, design context, screenshot, and variables.

## Goal

Generate a runnable MiniApp page that preserves Figma visual language through `@everly/miniapp-uidesign`, while sourcing health data from `@everly/miniapp-network`.

The page should be visually high fidelity for tokens, typography, spacing, surface style, colors, and UI tone. Data copy and sections may adapt when a Figma concept has no valid Health KV mapping.

## Hard Rules

- Do not modify `app/**` for generated MiniApp work.
- Do not blindly paste Figma reference code. Figma may return React + Tailwind code; adapt it to the project stack.
- Health values shown in UI must come from `@everly/miniapp-network`, or be derived from those values.
- If no Health KV key matches a visible health concept, use a close valid key, derive conservative copy from valid keys, or remove/reshape that UI. Do not invent data.
- Reusable visual tokens and components belong in `@everly/miniapp-uidesign`, not only in `src/miniapp/App.tsx`.
- Before creating a new style family, inspect existing `packages/miniapp-uidesign/src/styles/**`. Reuse exact matches. If close but different, ask whether to update the existing style or create a new family.

## Package Shape

Create or extend:

```text
packages/miniapp-uidesign/
  package.json
  src/
    index.ts
    styles/
      nutrition-green-report/
        tokens.ts
        components.tsx
    health-patterns/
      nutrition.tsx
```

Root wiring:

- Add `"@everly/miniapp-uidesign": "file:packages/miniapp-uidesign"` to root `package.json`.
- Add `transpilePackages: ['@everly/miniapp-uidesign']` to `next.config.ts`.
- Update `package-lock.json`. If `mise run install` is `npm ci`, first run `npm install --package-lock-only` or `npm install`, then verify with `mise run install`.

Minimal package manifest:

```json
{
  "name": "@everly/miniapp-uidesign",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "main": "src/index.ts",
  "types": "src/index.ts"
}
```

## Token Extraction

Create a style family named for the Figma visual language, for example `nutrition-green-report`.

Capture:

- page background and gradients
- surface, muted surface, chip, icon, border colors
- primary/secondary text colors
- brand/accent/status colors
- radius scale
- spacing scale
- shadows
- type family and type scale

If Figma variables are empty, use observed extracted styles and note that source is screenshot/design-context derived.

## Nutrition Health KV Mapping

Use this first-pass mapping for nutrition reports:

| Figma concept | Primary key | Fallback/action |
| --- | --- | --- |
| Daily totals | `nutrition_daily_totals` | use primary |
| Macronutrients | `nutrition_daily_totals.macros`, `protein_g`, `carbs_g`, `fat_g`, `sugar_g` | use primary |
| Calorie progress/advice | `nutrition_progress_status` | fallback to `nutrition_daily_totals.body` |
| Today's meals | `nutrition_meals_today` | empty state |
| Meal gallery | `nutrition_gallery_photos` | derive gallery cards from meals |
| AI reasoning | none | derive conservative text from valid nutrition data |
| Digestion-only labels | none | convert to nutrition labels or remove |

Useful imports:

```ts
import {
  createMiniappClient,
  type HealthKVResult,
  type NutritionDailyTotals,
  type NutritionGalleryPhoto,
  type NutritionMeal,
  type NutritionProgressStatus,
} from '@everly/miniapp-network'
```

Fetch the core nutrition page data in parallel:

```ts
const [totalsResult, progressResult, mealsResult, photosResult] = await Promise.all([
  client.getHealthKV('nutrition_daily_totals', { tz, includeSchema: true }),
  client.getHealthKV('nutrition_progress_status', { tz, includeSchema: true }),
  client.getHealthKV('nutrition_meals_today', { tz, includeSchema: true }),
  client.getHealthKV('nutrition_gallery_photos', { tz, includeSchema: true }),
])
```

## Implementation Sequence

1. Read the target repo rules. In `miniapp-sandbox`, generation normally stays in `src/miniapp/App.tsx`, but the user explicitly allows reusable D2C style/package files for `@everly/miniapp-uidesign`.
2. Inspect existing package, token, and MiniApp patterns.
3. Create or extend the style family under `packages/miniapp-uidesign/src/styles/`.
4. Create or extend health-pattern components under `packages/miniapp-uidesign/src/health-patterns/`.
5. Export only the intended public API from `packages/miniapp-uidesign/src/index.ts`.
6. Wire root dependency and Next transpilation.
7. Replace or update `src/miniapp/App.tsx` to orchestrate data fetching, state, auth token input, error handling, and composition of uid components.
8. Keep `src/miniapp/App.tsx` page-specific. Do not bury reusable tokens/components there.

## Verification Checklist

Run:

```bash
npm install --package-lock-only
npm install
mise run install
mise run check
mise run build
```

Then start local preview:

```bash
npm run dev -- -p 3000
curl --noproxy '*' -I http://localhost:3000
```

If localhost curl returns `502`, retry with `--noproxy '*'`.

Expected:

- `node_modules/@everly/miniapp-uidesign` links to `packages/miniapp-uidesign`.
- `mise run check` exits 0. A Next warning about dynamic `<img>` can be acceptable for Health KV image URLs in static H5/WebView targets.
- `mise run build` exits 0 and `/` is statically generated.
- Local preview returns HTTP 200 and contains key page text.

## Known Gotchas

- `mise run dev -- --port 3000` may pass arguments incorrectly; use `npm run dev -- -p 3000`.
- `next build` may rewrite `next-env.d.ts` between dev and production route type files. Do not keep that unrelated generated diff unless the user asks.
- antd-mobile component `style` props may type only specific CSS variables. Prefer standard CSS properties unless the variable is typed.
- If using native `<img>` for dynamic Health KV URLs, document the Next lint warning instead of switching to `next/image` without evaluating static export behavior.
