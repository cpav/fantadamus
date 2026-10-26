# Runbook: GitHub settings at the remote go-ahead

The gates on GitHub depend on these settings (R2.12). The owner applies them once, when creating the public
repository in task 15.1, and the remote checklist in task 15.2 proves they work. If GitHub's screens have
moved, the setting's name is what counts.

## 1. Repository

- [ ] Create the repository as **public**, with `main` as the default branch and no template files (the
      README, licence notice and `.gitignore` come from the first push).
- [ ] Settings → General → Pull Requests: allow **squash merging** only; turn on "Automatically delete head
      branches".

## 2. The `main` ruleset

Settings → Rules → Rulesets → New branch ruleset:

- [ ] Name `main`, enforcement **Active**, target: the default branch.
- [ ] **Bypass list: empty**, not even the owner, so every change goes through a pull request (R2.7).
- [ ] **Restrict deletions** (R2.3).
- [ ] **Block force pushes** (R2.3).
- [ ] **Require a pull request before merging**, with 0 required approvals (a single owner) and
      **Allowed merge methods: Squash** (R2.2, R2.4).
- [ ] **Require status checks to pass**, adding the checks `check` and `pr` from the `ci` workflow, with
      **Require branches to be up to date before merging** (R2.5, R2.6).

## 3. Security

Settings → Advanced Security (called "Code security" on some accounts):

- [ ] **Secret scanning** on (R10.7).
- [ ] **Push protection** on (R10.7).

## 4. Actions

Settings → Actions → General:

- [ ] Fork pull request workflows: **Require approval for all outside collaborators** (R12.8).
- [ ] Workflow permissions: **Read repository contents** (the workflows also set this themselves, R12.4).

## 5. The identity list

The identity check fails closed without the list, so CI needs it (R10.4). Use the same names as
`[creators] identities` in the private configuration, one per line.

- [ ] Settings → Secrets and variables → Actions: repository secret `FANTADAMUS_CREATOR_IDENTITIES`.
- [ ] Settings → Secrets and variables → **Dependabot secrets**: the same secret, so Dependabot pull requests
      pass the check too.

## Afterwards

Task 15.2 checks that the settings work. It uses throwaway branches, deleted afterwards:

- a failing test blocks the merge;
- a direct push and a force-push to `main` are refused;
- push protection rejects a fake key;
- a non-Conventional pull-request title fails the `pr` check.

The results go in `docs/reports/gate-selftest-<date>.md`.
