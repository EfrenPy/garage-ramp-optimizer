# Signing the Windows .exe via SignPath Foundation

Out of the box the Windows executables produced by `build_exe.py` and
attached to every GitHub Release are **unsigned**.  Users have to click
through Microsoft SmartScreen ("Windows protected your PC -> More info
-> Run anyway") on every download.

The cheapest way to remove that warning permanently is to sign the
binaries with a real Authenticode code-signing certificate.  The
[SignPath Foundation][spf] sponsors free code-signing for qualifying
open-source projects via their hosted CI integration -- no
certificate purchase, no USB token, no juggling of secrets.

[spf]: https://signpath.org/

This document is the application checklist for that programme, plus
the exact CI changes that need to land on `main` once the project is
approved.

## Prerequisites

- [ ] **MIT (or other OSI-approved) license**.  We already ship MIT
      via `LICENSE` -- nothing to do.
- [ ] **Public GitHub repository**.  `EfrenPy/garage-ramp-optimizer`
      qualifies.
- [ ] **A real, distinct project**.  SignPath rejects forks and
      thin wrappers; this project clearly meets the bar.
- [ ] **Working unsigned release pipeline**.  `release.yml` already
      builds `rampa-en.exe` / `rampa-es.exe` and attaches them to
      the GitHub Release.  We just need to insert a "sign" step
      between the build and the publish.

## Application steps

1. **Sign up** at <https://app.signpath.io/Web/SignUp>.  Pick the
   "Open Source / non-commercial" plan; SignPath Foundation
   sponsors it for free.
2. **Create an organisation** under your account
   (e.g. `efrenpy-oss`).  This is the SignPath equivalent of a
   GitHub org.
3. **Submit the project** at
   <https://app.signpath.io/Web/Documentation/RequestProject>.
   Fill in:
   - Repository URL: `https://github.com/EfrenPy/garage-ramp-optimizer`
   - License: MIT (link to `LICENSE`)
   - Maintainer email: efrenrguezrguez@gmail.com
   - Short description: see `README.md` opening paragraph
   - Build pipeline: GitHub Actions (`release.yml` -> `release-please.yml`)
4. **Wait for approval**.  Their volunteers manually vet every
   submission to keep the trust pool clean; budget 1-2 weeks.  They
   may ask for a screenshot, the README, or a build log.
5. **After approval** SignPath sends:
   - An **Organisation ID** (UUID)
   - A **Project Slug** (typically the repo name)
   - A **Signing Policy Slug** (`release-signing` is conventional)
   - A short-lived **API token** for CI use

## Wiring it into the release pipeline

Once those four IDs are in hand, do the following on `main`:

1. **Store the API token as a GitHub Actions secret**:
   - Settings -> Secrets and variables -> Actions -> New repository
     secret
   - Name: `SIGNPATH_API_TOKEN`
   - Value: the token from SignPath
2. **Add a signing job to `release.yml`** between
   `build-windows-exe` (Windows) and `publish-release` (Ubuntu).
   The official action is `signpath/github-action-submit-signing-request@v1`
   and its usage is documented at
   <https://about.signpath.io/documentation/integrations/github>.
   Sketch:

   ```yaml
   sign-windows-exe:
     name: Sign Windows .exe (${{ matrix.label }})
     needs: build-windows-exe
     runs-on: ubuntu-latest
     strategy:
       fail-fast: false
       matrix:
         outname: [rampa-en.exe, rampa-es.exe]
     steps:
       - uses: actions/download-artifact@v8
         with:
           name: ${{ matrix.outname }}
           path: unsigned
       - name: Submit signing request
         uses: signpath/github-action-submit-signing-request@v1
         with:
           api-token:        ${{ secrets.SIGNPATH_API_TOKEN }}
           organization-id:  <ORG_UUID>
           project-slug:     garage-ramp-optimizer
           signing-policy-slug: release-signing
           github-artifact-name: ${{ matrix.outname }}
           wait-for-completion: true
           output-artifact-directory: signed
       - uses: actions/upload-artifact@v4
         with:
           name: ${{ matrix.outname }}-signed
           path: signed/${{ matrix.outname }}
           retention-days: 1
   ```

3. **Update `publish-release`** to download the `*-signed` artifacts
   instead of the raw build artifacts, and rename them back to
   `rampa-en.exe` / `rampa-es.exe` before passing them to
   `softprops/action-gh-release`.

4. **Test on a pre-release tag** first (e.g. `v0.7.1-rc1`).  The
   SignPath portal lets you inspect each request before signing,
   so a few rejected dry runs cost nothing.

## Post-approval flip-the-switch checklist

The CI changes described above are pre-staged on the
`signpath/wire-up` branch.  When SignPath sends the approval email,
follow these exact steps to flip the switch:

1. **Open the email** from SignPath -- it contains four values:
   the Organisation ID (UUID), the Project Slug, the Signing-Policy
   Slug, and the CI user API token.  The token is shown **once**;
   copy it into a password manager immediately.
2. **Add the GitHub secret**:
   - Repo Settings -> Secrets and variables -> Actions -> New
     repository secret.
   - Name: `SIGNPATH_API_TOKEN`
   - Value: the token from the email.
3. **Replace the two TODO placeholders** in
   `.github/workflows/release.yml` on the `signpath/wire-up` branch:
   - `organization-id:      00000000-0000-0000-0000-000000000000`
     -> the Organisation UUID.
   - `project-slug:         garage-ramp-optimizer`
     -> verify this matches the slug SignPath assigned (usually it
     does, but pick whatever they emailed).

   The signing-policy slug is **resolved at runtime** from the tag
   shape (see the "Resolve target tag and signing policy" step):
   - stable tags `vX.Y.Z` -> `release-signing`
   - pre-release tags `-rc/-alpha/-beta/-pre` -> `test-signing`

   If SignPath only ships *one* policy for this project, edit that
   resolve-step to point both branches at the same slug, or rename
   the slug in the resolve-step to whatever they actually created.
4. **(Recommended) reply to the SignPath approval email** asking
   them to create **two** signing policies: `release-signing` (with
   manual approval per submission, gated by the maintainer) and
   `test-signing` (auto-approved, restricted to tags matching
   `v*-(rc|alpha|beta|pre)*`).  That mirrors what the CI now
   expects and lets rc tags smoke-test the pipeline without
   maintainer paging.  If they refuse, fall back to a single
   policy per the previous step.
5. **Open a PR** from `signpath/wire-up` to `main` titled
   `ci: enable SignPath code-signing on release` and merge it once
   green.
6. **Cut a release-candidate tag** -- e.g. `v0.7.3-rc1` -- via
   `workflow_dispatch` on `release.yml`.  The pipeline will route
   it to the `test-signing` policy automatically.  Verify with
   `signtool verify /pa /v rampa-en.exe` (or right-click ->
   Properties -> Digital Signatures) that the signed `.exe` lands
   on the rc release.
7. **Cut the real release** the normal way (let release-please merge
   its PR).  Both `rampa-en.exe` and `rampa-es.exe` should now ship
   signed under `release-signing`.

If anything goes wrong, the build/sign/publish jobs each produce
self-contained logs in the Actions tab.  The most common failure
mode is a typo in the Organisation UUID -- the SignPath action
returns a clear 401 in that case.

## Things to watch out for

- **Reproducible-ish builds**.  SignPath verifies via GitHub OIDC
  that the binary they sign was produced by the same workflow run
  that submitted it; the workflow stays self-contained
  (`build -> sign -> publish` in one run) so this is satisfied
  automatically.  On top of that, `release.yml` passes
  `--rebuild-bootloader` to `build_exe.py` so the PyInstaller
  bootloader is compiled locally from source on `windows-latest`
  instead of using the prebuilt PyPI bootloader -- this gives
  every release a unique bootloader hash, accelerating SmartScreen
  reputation accumulation against our SignPath certificate and
  dodging the bulk-AV heuristics that flag the off-the-shelf
  PyInstaller bootloader.
- **Reputation still has to build up**.  Even with a valid
  signature SmartScreen will warn for the first few thousand
  downloads.  Each new release inherits the certificate's
  reputation, so the warnings disappear once the cumulative volume
  is high enough; until then, signed binaries already get a
  reduced warning ("Don't run / Run anyway") instead of the scary
  "Windows protected your PC" overlay.
- **Don't commit the API token**.  Treat `SIGNPATH_API_TOKEN` like
  any other production credential.
- **Independent of SmartScreen**, the binary is still subject to
  Microsoft Defender heuristics; if false positives persist after
  signing, submit individual versions to
  <https://www.microsoft.com/en-us/wdsi/filesubmission>.
