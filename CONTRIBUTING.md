# Contributing

Thank you for helping improve Household Financial Planner.

## Before starting

- Search existing issues and pull requests.
- Open an issue before a large feature or schema change.
- Keep shared financial logic country-neutral.
- Add local rules through the provider registries instead of jurisdiction checks in shared code.
- Never commit real financial data, identities, credentials or tokens.
- AI assistants are permitted, but contributors remain responsible for every line they submit.
  Review generated changes personally and thoroughly before opening a pull request.

## Development workflow

1. Fork the repository and create a focused branch from `develop`.
2. Make the smallest coherent change.
3. Add or update tests; behaviour without relevant tests is incomplete.
4. Run the Python 3.14 backend quality image and Appsmith export tests from the root README.
5. Update user and operator documentation.
6. Open a ready-for-review pull request targeting `develop` using the repository template.

`develop` is the integration branch for tested changes; `main` contains stable releases. Release
pull requests promote `develop` to `main`. Never rewrite a migration that has appeared in a release;
add a new migration with tested upgrade and downgrade paths instead.

Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) for commit messages:
`type(optional-scope): concise description`. Common types are `feat`, `fix`, `docs`, `test`,
`refactor`, `build`, `ci`, `chore`, `perf` and `revert`. Mark incompatible changes with `!` before
the colon and include a `BREAKING CHANGE:` footer.

## Style and architecture

- Use Australian English in documentation where practical.
- Use Ruff formatting and linting and strict mypy.
- Use Pydantic schemas at API boundaries.
- Use `pydantic-settings` for configuration and `structlog` for API logging.
- Keep formulas in tested FastAPI modules, not Appsmith expressions.
- Preserve the distinction between observed, planned and projected data.

See [Architecture principles](docs/architecture-principles.md) and
[Code organisation](docs/code-organisation.md).

## Reporting security problems

Do not open a public issue for a suspected vulnerability. Follow [SECURITY.md](SECURITY.md).

By contributing, you agree that your contribution is licensed under GPL-3.0-only.
