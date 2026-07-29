# Release process

1. Ensure `develop` is clean and all CI checks pass.
2. Update the API and package version, changelog, README and upgrade documentation.
3. Run the full Python 3.14, Appsmith, migration, Compose and security checks.
4. Review the disclaimer, licence, third-party dependencies and generated Appsmith export.
5. Open a release pull request from `develop` into `main` and merge it with a normal merge commit,
   not a squash. This preserves ancestry between the two long-lived branches.
6. Include `Closes #123` entries for every issue delivered by the release. GitHub applies automatic
   closing keywords when this pull request reaches the default `main` branch.
7. Create an annotated `vX.Y.Z` tag on the merge commit and push it.
8. Publish a GitHub Release from that tag using the matching changelog section.
9. Build the tagged runtime image and perform a fresh-install smoke test.

Tags and GitHub Releases must point to `main`, never an unmerged release branch.
After the initial v1.0.0 release, create `develop` from the tagged release commit. Do not rewrite or
squash the repository's existing published history; the release tag is the clean baseline for the
new workflow.
