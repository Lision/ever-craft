---
name: frontend-pr
description: >-
  Publish a GitHub pull request from the current task worktree with focused commits,
  risk notes, and UI comparisons. Use when the user's entire trimmed message is
  lowercase `pr`, or they explicitly request opening a pull request.
  DO NOT activate for questions, reviews, description-only drafts, or edits to this skill.
---

# Frontend PR

Treat an explicit PR request as authorization to commit and push the task changes and open a reviewable PR. Keep the task branch and worktree. DO NOT merge the PR or delete branches, worktrees, or build artifacts without separate authorization.

## 1. Identify the worktree and target

- Use task context, `git worktree list --porcelain`, `git status --short --branch`, and `git remote -v` to identify the worktree, named task branch, push remote, and head/base repositories. Run subsequent commands in that worktree.
- Ask for clarification if multiple worktrees fit, HEAD is detached, the checkout is an integration branch, or remote ownership is unclear.
- Use the user's explicit base repository and branch. Otherwise, use the branch from which the task branch was actually created. Preserve creation evidence before setting an upstream.
- Accept a recorded creation command, a named starting ref in `git reflog show --format='%gs' refs/heads/<topic>`, or a matching checkout entry in the originating worktree's HEAD reflog. A branch created from `origin/release/1.2` targets `release/1.2` in that remote's repository.
- DO NOT infer the source branch from a commit SHA, `Created from HEAD`, the push upstream, the nearest merge-base, or the repository default. Git history does NOT record branch names. Ask for the target if evidence is missing, contradictory, or points to a deleted branch.
- Find open PRs for the head branch across all bases, then verify head repository identity:

  ```bash
  gh pr list --repo "$base_repo" --state open --head "$topic" \
    --json number,url,headRepositoryOwner,headRepository,baseRefName
  ```

  Reuse a PR with the same head repository, branch, and base. If only a different-base PR exists, ask whether to retarget it or open another. DO NOT silently retarget or duplicate a PR.

## 2. Commit the task changes

- Inspect `git diff --cached`, `git diff`, and `git ls-files --others --exclude-standard`; read relevant untracked files.
- Group all task changes into independently reviewable commits. Stage by path or hunk, inspect each staged diff, and follow repository commit conventions. Regroup mixed staged changes while preserving working files.
- Ask about changes whose ownership is unclear. DO NOT include unrelated edits, credentials, ignored build output, or review screenshots.
- Check for unpushed commits even when the worktree is clean. Confirm the complete task scope is represented in the commit history.

## 3. Synchronize, validate, and push

- Fetch the confirmed target remote. Set `base_ref` to the freshly fetched remote-tracking ref for the target branch.
- Run `git merge-base --is-ancestor "$base_ref" HEAD`. On exit 1, merge that ref into the task branch; on any other failure, diagnose it before proceeding.
- Preserve both sides' intended behavior when resolving conflicts. Ask the user to decide unresolved product behavior.
- Run the affected lint, tests, and builds required by the repository. Record commands and results. Fix failures caused by this task and commit the fixes. Report blockers and existing failures accurately; DO NOT claim validation passed when it did not.
- Review `git diff --stat "$base_ref"...HEAD` and `git diff "$base_ref"...HEAD`. If there is no PR diff, report that result and stop.
- Push the task branch to the verified remote under the same name. DO NOT force-push, including `--force-with-lease`. If the remote is ahead, fetch, inspect, merge its changes, resolve conflicts, and rerun affected checks before retrying.
- Verify that the remote head SHA equals the validated local HEAD. Use that SHA for the final review and UI evidence. If HEAD changes later, repeat the affected validation and evidence checks.

## 4. Prepare UI evidence and the PR body

For visible changes, follow [UI evidence](references/ui-evidence.md). This skill includes the capture procedure and comparison script; no separate skill is required. Use `git merge-base "$base_ref" HEAD` as the PR baseline and the validated, pushed HEAD as the reviewed revision. Reuse verified screenshots or builds before rebuilding. Omit images for changes with no visible effect.

Write the title and body in the user's or repository's working language. Follow the repository PR template where present. Summarize the final diff with one short bullet per meaningful change:

- Start routine changes with `- ✅`.
- Start compatibility, data, or material review risks with `- ⚠️`; add one indented bullet specifying the behavior to check. DO NOT invent risks to fill a category.
- Place each comparison after the summary, with descriptive alt text. Follow the images with the actual validation results and any missing evidence or blockers.

```markdown
- ✅ Allow weight entries for past dates from the weekly calendar.
- ⚠️ Include the local UTC offset in weight-entry requests.
  - Verify the offset when backdating an entry to 23:59 on a daylight-saving transition day.

![Past-date entry: before on the left, after on the right](./weight-entry.png)

Validation: <commands and actual results>. UI capture: <device and OS>.
```

## 5. Publish and verify

- Recheck open PRs before publishing. Update the matching PR and preserve content maintained by others.
- Write the complete body to a temporary Markdown file outside the repository. Place comparison images beside it. Check the installed `gh pr create --help` or `gh pr edit --help` for attachment support.
- For a same-repository PR, use explicit head and base arguments:

  ```bash
  gh pr create --repo "$base_repo" --base "$base_branch" --head "$topic" \
    --title "$title" --body-file "$review_dir/body.md" \
    --attach "$review_dir/weight-entry.png"
  ```

  Replace the example filename; repeat `--attach` for each image and omit it when no images are needed. For a fork, explicitly identify its owner and branch using the installed CLI's supported syntax. DO NOT allow the CLI to infer a different head repository.
- Use `gh pr edit` with the PR identifier and repository for an existing PR. Preserve valid uploaded image URLs; attach only new or replaced images.
- If `gh` is unavailable or required attachments are unsupported, report the blocker and retain the prepared body and images. DO NOT present a local image path as published evidence.
- A failed attachment upload may still create or update the PR. Recover it from the returned URL or the exact head/base match, inspect the body, and retry only missing uploads. DO NOT create a duplicate PR. If the same upload fails again, retain the artifacts and report the unresolved blocker.
- Use `gh pr view` to verify the PR is open, its base and head repository/branch are correct, its head SHA matches the validated revision, and its body contains every expected image as a reviewer-accessible remote URL. DO NOT claim an image is accessible unless checked.
- Return the PR URL, target branch, validation results, and any unfinished items. Stop after publication and verification.
