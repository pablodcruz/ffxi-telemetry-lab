# FFXI Telemetry public dashboard

The privacy-reviewed, static aggregate view published at
[ffxi-telemetry.pablo-de-la-cruz-pro.chatgpt.site](https://ffxi-telemetry.pablo-de-la-cruz-pro.chatgpt.site).

This site contains no raw telemetry, row-level records, credentials, agent IDs,
lease IDs, target names, or full Git SHAs. Its values are copied only from the
reviewed public snapshot produced by the parent analytics repository.

Requires Node.js 22.13 or later.

```bash
npm install
npm run build
npm test
npm run build:vercel
```

`npm test` rebuilds the site and checks its server-rendered output, public
metadata, privacy language, aggregate headline values, and removal of starter
preview content.

The default build remains the Sites/Vinext target. `build:vercel` performs a
native Next.js production build, and `vercel.json` selects it when this
directory is deployed as a Vercel project. Set the Vercel project root
directory to `site`.
