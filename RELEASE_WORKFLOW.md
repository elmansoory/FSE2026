# FSE Release Workflow

This repository is the release-tracking backbone for FSE builds.

## Standard release structure

Each release should live in its own folder under `releases/` using this naming pattern:

- `releases/v2_8_2/`
- `releases/v2_9/`
- `releases/v3_0/`

## Minimum files for each release

- `README_<version>.md`
- `OWNER_<version>_SUMMARY.json`
- main app file or main script
- Windows launcher `.bat`
- key export reports
- one short validation note if production accuracy is not yet confirmed

## Release steps

1. Build the local release package.
2. Generate the summary and exported reports.
3. Create the release folder inside `releases/`.
4. Add the release README and owner summary.
5. Add the launcher and main app or core script.
6. Add the most important exported reports.
7. Update `README.md` and `releases/README.md`.
8. Keep the notes honest: do not claim production accuracy unless benchmark evidence exists.

## Owner rule

- Operational data import is not the same as model validation.
- Benchmarks must be backed by trusted labeled clips.
- Every new release should be easy to inspect, run, and audit from GitHub.
