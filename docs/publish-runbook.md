# Ciralgo Python SDK release runbook

Audience: any engineer cutting a new release of the `ciralgo` Python package on PyPI.

> **Pre-flight requirement:** the one-time maintainer bootstrap (PyPI namespace claim, Trusted Publishing OIDC configuration, and the `pypi` GitHub environment with required-reviewer protection) must already be in place. That is a one-time setup performed outside this repo by a maintainer with PyPI account access. This runbook covers the steady-state release flow only. If you are reading this before bootstrap is complete, releases will fail at the OIDC auth step and the tag will be stuck. See the troubleshooting section below.

## How a release flows

The full chain is automated. There is no manual `twine upload` step. Trusted Publishing handles auth via OIDC.

```
1. Engineer bumps version in pyproject.toml
2. Engineer creates tag `sdk-py-v<X.Y.Z>` matching the pyproject version
3. Engineer pushes the tag
4. GitHub Actions runs sdk-python.yml:
     - `test` job  → Python 3.9/3.10/3.11/3.12 matrix
     - `build` job → builds sdist + wheel
     - `publish` job → BLOCKED by `pypi` environment
5. Required reviewer approves the deployment in the GitHub Actions UI
6. `publish` job authenticates to PyPI via OIDC and uploads
7. Package available at https://pypi.org/project/ciralgo/<X.Y.Z>/
```

## Cutting a release

### 1. Pick the version

Follow semver. The SDK version intentionally mirrors the Ciralgo OpenAPI spec `info.version` so a customer reading "API 1.2.0" and `pip install ciralgo==1.2.0` end up at compatible surfaces.

- Patch bump (`1.1.0` → `1.1.1`): bug fix only, no new surface.
- Minor bump (`1.1.0` → `1.2.0`): new endpoint covered, additive.
- Major bump (`1.1.0` → `2.0.0`): breaking change in client surface.

### 2. Update `pyproject.toml`

```
pyproject.toml line 7:  version = "1.2.0"
```

Commit on a branch, open a PR, get it merged. The CI test matrix on the PR will run against the new version automatically.

### 3. Tag from `main` after merge

```
git checkout main
git pull
git tag sdk-py-v1.2.0
git push --tags
```

The tag MUST match `^sdk-py-v(.+)$`. The workflow filters on this pattern. A tag like `v1.2.0` or `python-sdk-1.2.0` will silently not trigger the publish flow.

The tag MUST match the `pyproject.toml` version exactly. The `build` job verifies this and fails loudly on mismatch.

### 4. Approve the deployment

When the `publish` job hits the environment gate, GitHub sends a "deployment waiting for review" notification to all required reviewers configured on the `pypi` environment.

1. Open the Actions tab: https://github.com/Ciralgo/ciralgo-python/actions/workflows/sdk-python.yml
2. Click the running workflow.
3. Click "Review deployments".
4. Check `pypi`, leave an approval comment (e.g. "1.2.0: embeddings + usage endpoint coverage"), click "Approve and deploy".

The publish job runs, OIDC auth happens, the package uploads, the job goes green.

### 5. Post-release verification

```
pip install --upgrade ciralgo==1.2.0
python -c "import ciralgo; print(ciralgo.__version__)"
# Expected: 1.2.0
```

Open https://pypi.org/project/ciralgo/1.2.0/ and confirm:
- README rendered.
- License = Apache-2.0.
- Author = Ciralgo (support@ciralgo.com).
- Long description body matches what we expect (no leftover dev placeholders).

### 6. Update the CHANGELOG

Add the release line to the top-level `CHANGELOG.md` `## [Unreleased]` block, then promote to a versioned heading on the next overall platform release.

## Troubleshooting

### Workflow does not trigger after `git push --tags`

- Verify the tag matches `sdk-py-v*`.
- Verify the tag was actually pushed: `git ls-remote --tags origin | grep sdk-py-v`. If missing, `git push --tags` again.

### `build` job fails with "tag version does not match pyproject version"

- Operator error. The tag and `pyproject.toml` version must match exactly.
- Fix: delete the tag locally + remote, bump pyproject correctly, re-tag.
- `git tag -d sdk-py-v1.2.0 && git push --delete origin sdk-py-v1.2.0` then redo.

### `publish` job fails with `Token request failed` or `OIDC token invalid`

- The Trusted Publishing config on PyPI does not match the workflow context. Check:
  - PyPI publisher: owner = `Ciralgo`, repo = `ciralgo-python`, workflow = `sdk-python.yml`, environment = `pypi`.
  - Workflow YAML: `environment.name: pypi`, `permissions: id-token: write`.
  - The tag was pushed from a branch in the `Ciralgo` org repo, not a fork.

### `publish` job is stuck waiting for review

- Whoever has reviewer rights on the `pypi` environment needs to approve.

### A previously-published version needs to be unpublished

- You cannot. PyPI does not allow re-uploading an already-published version, even after deletion.
- Cut a new patch release with the fix. Yank the bad version (PyPI > project > Releases > Yank) so `pip install ciralgo` skips it.

## Defensive squat names

To prevent typo-squat backdoors, these four placeholder packages are owned by us and all point to the canonical `ciralgo` package as their sole dependency:

| Squat name | Purpose |
|---|---|
| `ciralgo-sdk` | Most common typo (developer assumes "official SDK" suffix). |
| `ciralgo-python` | Common typo (developer assumes language suffix). |
| `ciralgo-client` | Common typo (developer assumes client/server distinction). |
| `ciralgo-api` | Common typo (developer assumes API client suffix). |

These are owned by the maintainer account. Do NOT publish new versions of them. The 0.0.1 placeholder is sufficient to lock the name.
