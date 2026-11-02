# ElicitSense web demo

Static Next.js site for the ElicitSense demo: the requirements register with
playable evidence, changes by meeting, recorded Q&A answers with checked
citations, and the evaluation tables. It needs no API key; every output it
shows comes from real pipeline runs exported by `elicitsense export-demo`.

```bash
# from the repository root: refresh the demo data from the latest runs
uv run elicitsense export-demo data/projects/harbour_physio data/projects/fernhill_bakery -o web/public/demo

cd web
npm install
npm run dev      # http://localhost:3000
npm run build    # static site in web/out
```

Deploy: import the repository on Vercel with `web` as the root directory (the
build is a static export), or upload `web/out` to any static host.

To publish under a sub-path of another static site (for example a GitHub Pages
personal site), build with the base path and copy the output:

```bash
DEMO_BASE_PATH=/demos/elicitsense npm run build
rsync -a --delete out/ ../../personal-website/demos/elicitsense/
```
