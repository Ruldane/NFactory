<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## NFactory dashboard

- **Data**: the browser calls same-origin `/api/v1/*`, which `next.config.ts` rewrites to the API. `API_INTERNAL_URL` is read at build time, because Next 16 has no runtime config. Fetch through the TanStack Query hooks in `lib/api/queries.ts`, typed by `lib/api/types.ts`.
- **UI kit**: shadcn "base-nova" on `@base-ui/react`, not Radix. `cn` comes from the `cn` npm package.
- **Design**: tokens live in `app/globals.css`. The palette is cream, eggplant, navy, coral, coral-deep, butter and forest. Fonts are Fraunces for display, Instrument Sans for body, JetBrains Mono for data.
- **Accessibility**: a state always shows a glyph plus a French label, never color alone. The mapping lives in `lib/run-state.ts`.
- **Text**: UI text in French, code comments in English. Missing values render as "—" or "Non mesuré", never as a fake zero; see `lib/format.ts`.
- **Tests**: Vitest + jsdom + Testing Library, without `@vitejs/plugin-react` because it conflicts with the shadcn CLI's Babel. Tests sit next to their source as `*.test.ts(x)`.
