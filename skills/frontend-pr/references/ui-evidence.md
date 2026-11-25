# UI Evidence

Read this reference when the PR changes layout, spacing, color, typography, icons, copy, assets, or visible component states. Produce one Before/After image per visually distinct change, with Before on the left and After on the right. Group related changes only when a shared crop makes them clear.

## Choose and verify the baseline

1. List the affected screens and states from the task and final diff. Include relevant selected, error, empty, and long-text states. Record the intended capture profile.
2. Set the baseline to `git merge-base "$base_ref" HEAD` after synchronizing with the confirmed target. When this workflow starts before editing, record the initial SHA and capture reusable Before images; reconcile them with the PR baseline later.
3. Reuse an existing screenshot first, then a runnable build, and build the baseline only if neither is usable. Verify its actual source SHA, configuration, variant, fixtures, screen/state, and capture profile.
4. If the captured SHA differs from the required revision, inspect `git diff --name-status "$captured_sha" "$required_sha"` and the relevant diff. Reuse only when the differences cannot affect the captured UI, resources, dependencies, fixture, or build configuration. Record the actual SHA and the equivalence rationale. DO NOT relabel an older capture as the required revision.
5. If equivalence cannot be established, capture the required revision. Use an isolated checkout for baseline builds when the task already contains changes. DO NOT reset or overwrite the task worktree. Reuse locked dependencies and project build settings.

Use the same provenance checks for After, targeting the validated, pushed HEAD. Screenshot reuse does NOT replace validation of that revision. Iteration-to-iteration comparisons may help a design discussion; DO NOT substitute them for merge-base-to-head PR evidence.

## Capture matching states

- Match device or browser, OS, viewport, scale, appearance, text size, locale, build configuration, and variant.
- Use the same deterministic data, screen, scroll position, focus/selection, and scenario on both sides. Freeze clocks or other dynamic content where possible; wait for loading and animations to finish.
- Use the project's existing preview, test, or launch entry point. If a temporary fixture is necessary, apply the same fixture to both revisions, record it, and remove only those temporary edits afterward. DO NOT commit capture-only fixtures.
- Open both raw screenshots before composing. Confirm the intended screen is fully rendered and the state matches. DO NOT accept blank, half-loaded, or unrelated captures just because their pixels differ.
- Keep raw captures, comparisons, and a `capture.md` outside the repository. Use a persistent, repository-specific user cache for reusable artifacts; use a separate temporary review directory for uploads. DO NOT include personal account data or secrets in shared captures.
- In `capture.md`, record the actual capture SHA, baseline/reviewed SHA, equivalence rationale if needed, configuration and variant, scenario, fixture revision or launch arguments, temporary fixture edits, capture profile, raw image paths, and retained build path if any.

### iOS Simulator

Reuse a compatible Simulator app with verified provenance and follow the project's signing and installation checks. If a matching `.xctestrun` and all referenced products exist, use `xcodebuild test-without-building` for the capture case; otherwise install and launch the existing app if it can reach the state.

After installing, launch once to warm up, relaunch, and wait for the target screen to settle. Fix the status bar before each capture:

```bash
xcrun simctl status_bar "$udid" override --time 09:41 --batteryState charged --batteryLevel 100
xcrun simctl io "$udid" screenshot "$capture_dir/$point-before.png"
# Install and open the reviewed build in the matching state, then capture After.
xcrun simctl io "$udid" screenshot "$capture_dir/$point-after.png"
```

Record the simulator model, OS, appearance, Dynamic Type size, and locale. Restore status-bar overrides after capture if this workflow introduced them.

## Compose and inspect

The bundled [comparison script](../scripts/before_after.swift) requires macOS and Swift with CoreGraphics, CoreText, and ImageIO. It accepts equal-sized screenshots from any platform. Set `skill_dir` to the absolute directory containing this skill's `SKILL.md` and create the output directory before running it.

```bash
swift "$skill_dir/scripts/before_after.swift" \
  --before "$capture_dir/$point-before.png" --after "$capture_dir/$point-after.png" \
  --out "$review_dir/$point-before-after.png"

# Crop both sides to the same rectangle: x,y,width,height in pixels, origin top-left.
swift "$skill_dir/scripts/before_after.swift" \
  --before "$capture_dir/$point-before.png" --after "$capture_dir/$point-after.png" \
  --out "$review_dir/$point-before-after.png" --crop 0,380,1206,520
```

- Default mode groups changed rows into full-width bands with 60 pixels of vertical context. Bands separated by more than `--gap` rows (default 160) produce numbered files. Use the printed crop coordinates to refine them and rename files after the change they show.
- Use `--crop` to isolate a change or `--full` when a change affects the whole screen. DO NOT combine these options.
- Pixel comparison is exact by default. Use `--tolerance N` (0–255) only for known rendering noise and record the value. A tolerance can hide subtle intended changes; DO NOT use it to conceal mismatched captures.
- Exit 0 means images were written; exit 1 means invalid input or an I/O error; exit 2 means no pixels exceed the tolerance in the selected region. Exit 2 does NOT prove the task has no visual effect. Check the build, scenario, crop, and tolerance before deciding evidence is unnecessary.
- Automatic bands locate pixel differences, NOT semantic changes. Inspect every output for the intended change, matching states, legible context, and unrelated differences. Add context if the labels cover relevant content.
- On systems without the required Swift frameworks, use an available image compositor to produce the same labeled, equally cropped layout. DO NOT install new tooling without checking available capabilities; report a blocker if composition is unavailable.

Name final images `<branch-slug>-<point>-before-after.png`. Embed them after the PR summary using the publication steps in `SKILL.md`; include device/OS or browser/viewport details and identify any missing comparisons with their reason. DO NOT treat missing visual evidence as completed verification.
