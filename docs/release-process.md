# Release process

1. Ensure `main` is clean and all CI checks pass.
2. Update the API and package version, changelog, README and upgrade documentation.
3. Run the full Python 3.14, Appsmith, migration, Compose and security checks.
4. Review the disclaimer, licence, third-party dependencies and generated Appsmith export.
5. Merge the release pull request.
6. Create an annotated `vX.Y.Z` tag on the merge commit and push it.
7. Publish a GitHub Release from that tag using the matching changelog section.
8. Build the tagged runtime image and perform a fresh-install smoke test.

Tags and GitHub Releases must point to `main`, never an unmerged release branch.
