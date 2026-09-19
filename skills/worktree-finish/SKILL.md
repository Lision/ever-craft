---
name: worktree-finish
description: Finalize an accepted worktree in projects using parallel Git worktrees when the developer replies checked or cc, or explicitly requests this workflow. Commit and push changes, reconcile the target branch, clean verified worktree-specific build artifacts when applicable, and create and merge a pull request. Quoted trigger words or requests to edit this skill are not acceptance.
---

# Finish an Accepted Worktree

## Scope and Authorization

Use this workflow for development in isolated worktrees: one worktree per branch. A developer reply of `checked` or `cc` accepting the active worktree, or an explicit request to finish it with this skill, authorizes this entire workflow, including commits, pushes, targeted build-artifact cleanup, pull request creation, and merge. Do not ask for routine confirmation again. Ask the developer when a conflict requires an uncertain product or implementation decision.

Follow the project's applicable instructions and conventions. Creating or editing this skill does not invoke its workflow.

## 1. Identify the Accepted Worktree

Use the active task's worktree, which may differ from the shell's initial directory. Inspect `git worktree list --porcelain`, `git status --short --branch`, and the configured remotes and branch tracking. Run subsequent Git commands from that worktree. If the accepted worktree is ambiguous, ask the developer to identify it.

Identify the push remote, target repository, and target branch from the task, an existing pull request, or repository instructions. Otherwise use the target repository's confirmed default branch; do not assume it is named `main` or that its remote is named `origin`. In fork workflows, distinguish the head repository from the target repository. Resolve any ambiguity before pushing or merging.

Require a named topic branch other than the target branch or the repository's default branch. Never perform this workflow from either integration branch, a detached HEAD, or a different project's checkout. Finish or resolve an existing Git operation before starting another. Derive the hosting platform and repository identities from the remotes; do not assume the current CLI repository context is correct.

## 2. Commit and Push Local Changes

Inspect staged, unstaged, and untracked files, including their diffs. If local changes exist, stage the accepted worktree changes explicitly and create atomic commits following the repository's commit convention; use `type(scope): imperative summary` when no convention is specified. Exclude ignored build artifacts and credentials. If a change's ownership or inclusion is unclear, ask before including or discarding it.

Push the branch to the identified push remote and set its upstream when needed. If there are no local changes, skip this commit-and-push step; step 5 still publishes any existing unpushed commits needed for the pull request. Never force-push or reset away local work.

## 3. Reconcile with the Target Branch

Fetch the target remote and use its freshly fetched target branch as the pull request base. Inspect divergence and merge that base into the worktree branch when it is not already an ancestor. Do not switch to or edit the local target-branch checkout.

Resolve conflicts automatically only when the intended result is clear from both changes and the accepted behavior. Preserve both sides' intent; do not resolve by blindly choosing ours or theirs. For uncertain conflicts, show the affected files and competing behavior, ask a concise question, and pause the dependent workflow until answered.

Inspect the combined diff and run checks appropriate to the changes, using the repository's documented commands and CI configuration. Select relevant lint, tests, and builds for the project's toolchain; documentation-only changes generally need documentation checks rather than an application build. Commit resolved merges and push. If validation fails, diagnose and fix within the accepted scope; stop and explain blockers that need developer input.

## 4. Clean This Worktree's Build Artifacts When Applicable

After validation and once builds using the artifacts have finished, perform cleanup prescribed by the project or the applicable Xcode cleanup below. Delete only disposable build artifacts whose ownership by this worktree is verified. Skip cleanup when no applicable artifacts exist. Do not infer ownership from a project name, remove shared caches, or use a blanket clean command that could discard unrelated work. Report what was removed or skipped.

For Xcode projects, inspect the immediate child directories of `~/Library/Developer/Xcode/DerivedData/`. Read each directory's `info.plist` with `plistlib` or `plutil`. A directory belongs to this worktree only when its recorded `WorkspacePath`, after path normalization, equals the worktree root or lies beneath it on a complete path-component boundary. This covers generated `.xcworkspace` and `.xcodeproj` paths.

Delete only verified matching directories. Skip symlinks, unreadable or missing metadata, ambiguous ownership, and other worktrees' artifacts. Never delete the entire DerivedData directory. If none match, skip cleanup. Do not start further builds after cleanup unless necessary; repeat this targeted cleanup if they recreate matching artifacts.

## 5. Create and Merge the Pull Request

Ensure the remote worktree branch contains all accepted commits, including any merge-resolution commits. Use the hosting platform's available CLI or API with explicit target repository, head repository and branch, and base branch. Reuse an existing open pull request (or merge request) for that head/base pair; otherwise create one. If the branch is already integrated and has no remaining diff, report that instead of creating an empty request. If no supported hosting integration is available, report the published branch and the remaining merge step; do not substitute a direct push to the target branch.

Write a concise title and body describing the resulting behavior and validation. On GitHub, use `gh` with an explicit repository, head, and base, and a temporary body file with `--body-file` for multiline text. On other platforms, use the equivalent structured input or file option. Check the request's current head SHA, mergeability, and required checks. Wait for required checks; do not bypass branch protection or use administrator overrides. If the target branch advances and introduces conflicts, repeat reconciliation and validation before merging.

Merge with a repository-supported strategy and a guard that the head SHA still matches the verified commit. With `gh`, use `--match-head-commit <verified-head-sha>`; on other platforms, use the equivalent expected-head condition. If the integration cannot enforce this condition, report the limitation and leave the request open. Prefer a merge commit when allowed by repository policy. Do not delete the branch or worktree as part of this workflow. If a merge queue or required approval delays completion, report the actual pending state; do not claim a queued request is merged.

Verify the request is merged and report its URL, merged commit, validation, and artifact cleanup. Leave unrelated worktrees and their local changes untouched. Do not automatically pull into the original integration-branch checkout, which may contain local changes.
