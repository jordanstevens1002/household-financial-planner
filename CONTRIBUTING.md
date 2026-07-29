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

1. Start with an issue that explains the problem, desired outcome and acceptance criteria.
2. Split broad issues into independently reviewable vertical slices before implementation.
3. Fork the repository and create a focused branch from `develop`.
4. Make the smallest coherent change.
5. Add or update tests; behaviour without relevant tests is incomplete.
6. Run the Python 3.14 backend quality image and Appsmith export tests from the root README.
7. Update user and operator documentation.
8. Open a ready-for-review pull request targeting `develop` using the repository template.

`develop` is the integration branch for tested changes; `main` contains stable releases. Release
pull requests promote `develop` to `main` with a normal merge commit so the long-lived branches
retain shared ancestry. Feature pull requests are squash-merged into `develop`. Never rewrite a
migration that has appeared in a release; add a new migration with tested upgrade and downgrade
paths instead.

Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) for commit messages:
`type(optional-scope): concise description`. Common types are `feat`, `fix`, `docs`, `test`,
`refactor`, `build`, `ci`, `chore`, `perf` and `revert`. Mark incompatible changes with `!` before
the colon and include a `BREAKING CHANGE:` footer. Use the same form for the pull request title,
then reference the issue at the end, for example `feat(loans): compare repayment options (#123)`.
Use `Refs #123` in a feature pull request body because GitHub only applies automatic closing
keywords when a pull request targets the default branch.

## Pull request size

Aim for no more than approximately 750 human-reviewed changed lines when first opening a pull
request, leaving roughly 250 lines of headroom for review corrections. This is guidance rather than
a merge blocker: explain why a larger cohesive change cannot reasonably be split. A pull request
approaching 1,500 human-reviewed changed lines should normally be divided, and exceeding 1,500
requires explicit maintainer agreement.

The size guide counts additions and deletions. Deterministically generated exports, dependency lock
files, vendored code and snapshots are reported separately because reviewing their generators or
inputs is more useful than treating generated output as handwritten code. Database migrations,
tests and documentation count as human-reviewed changes.

Within a pull request, use separate conventional commits when they represent useful review units,
such as schema, backend, frontend and documentation changes. Fixup commits are acceptable during
review because the completed feature pull request is squash-merged into `develop`.

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
