# Repository Guidelines

## Project Structure & Module Organization
This repository is a Hexo-based blog. Write and edit content under `source/_posts/` (grouped by topic such as `network/`, `develop/`, `notes/`, `ai_tech/`, `ai_diary/`). Store reusable media in `source/images/` and article-specific images in `source/post-images/`. Scaffolds live in `scaffolds/` and define default front matter for new posts/pages. Treat `public/`, `.deploy_git/`, `node_modules/`, and `db.json` as generated/local artifacts (ignored by git).

## Build, Test, and Development Commands
Install dependencies:
```bash
npm install
```
Run local preview server (default `http://localhost:4000`):
```bash
npm run server
```
Generate static site output into `public/`:
```bash
npm run build
```
Clean cached/generated files before a fresh build:
```bash
npm run clean
```
Deploy using Hexo deploy targets configured in `_config.yml`:
```bash
npm run deploy
```

## Coding Style & Naming Conventions
Use Markdown with YAML front matter. Follow scaffold keys (`title`, `date`, `tags`, `categories`) and keep category names consistent with existing folders. Prefer lowercase, hyphen-separated filenames (for example, `openclaw-model-switching-troubleshooting.md`); date-prefixed names are used for diary/tech series (`YYYY-MM-DD-topic.md`). Use fenced code blocks with language identifiers (for example, ```bash).

## Testing Guidelines
There is no automated unit/integration test suite in this repository. Validation is content and build based:
- Run `npm run clean && npm run build` and ensure it finishes without errors.
- Run `npm run server` and spot-check changed pages, links, and images.
- If you change config/theme behavior, verify at least one related post render on desktop and mobile widths.

## Commit & Pull Request Guidelines
Recent history uses short, purpose-first subjects in either English or Chinese (examples: `add: ...`, `update: ...`, `添加 ...`). Keep commits focused to one logical change (new post, edit batch, config tweak). For PRs, include:
- clear summary and affected paths (for example, `source/_posts/ai_tech/`)
- linked issue/context when applicable
- screenshots for visual/layout/config changes
- confirmation that local build/preview checks were run

## Security & Configuration Tips
Do not commit secrets, private tokens, or real credentials in post examples or `_config*.yml`. Deployment requires valid SSH access to the Git remotes defined in `_config.yml`.
