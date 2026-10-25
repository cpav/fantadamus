# Runbook: a secret or a FantaCreator identity reached GitHub

The repository is public. The pre-commit and pre-push hooks are the preventive gates; CI and GitHub's push
protection catch what slips past them, but by then the commit may already be visible (R9.6, R10.8).
Act in this order, and fast: public repositories are scraped within minutes.

## A secret reached GitHub

1. **Rotate it first.** Revoke the key or token at its issuer (AWS IAM, the API provider) and issue a new
   one into private configuration or the CI secret. Assume the old value is compromised, whatever happens
   next; rewriting history doesn't un-leak it.
2. Check the issuer's logs (AWS CloudTrail for AWS keys) for any use since the commit was pushed.
3. Remove it from the branch: if the pull request isn't merged, close it and delete the branch; if it is,
   push a commit removing the value. Then follow "Removing it from history" below.
4. If GitHub's secret scanning raised an alert, resolve it as "revoked".

## A FantaCreator identity reached GitHub

1. Close the pull request and delete the branch. A squash merge keeps the PR's commits visible on GitHub,
   so a removal commit alone isn't enough.
2. If it reached `main`, push a commit removing it, then follow "Removing it from history" below.
3. Ask GitHub Support to purge cached views of the affected commits and pull request
   ([removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)).
4. Tell the creator only if the owner decides to; the identity list itself stays in private configuration.

## Removing it from history

Rewriting `main` needs the owner: it means temporarily allowing a force-push in the ruleset, which the
agent hooks block. Use `git filter-repo` on a fresh clone, force-push, restore the ruleset with
`make github-apply`, and have every clone re-cloned. GitHub may still hold the old commits in pull-request
refs and caches; step 3 above covers those.

## Afterwards

- Add a test that would have caught it (a gitleaks rule, or the identity in the private list), and confirm
  it fails on the leaked content.
- Record what happened, the timeline and the fix in `docs/reports/`, without repeating the leaked value.
