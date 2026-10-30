# Why creating the `ai-dev-company` repository returned 403

## Observed

```
POST https://api.github.com/user/repos  ->  403 Resource not accessible by integration
```

The call went through the GitHub tools of this Claude Code session. They act as the user `mhmadps386`
(confirmed with `get_me`) by way of the **Claude GitHub App**.

## Diagnosis

- "Resource not accessible by integration" is GitHub's standard error when a **GitHub App token** lacks
  the permission an endpoint needs. It is not a bad password, a missing scope on a classic PAT, or a rate limit.
- Creating a repository for a user (`POST /user/repos`) requires the **"Administration" repository
  permission (write)** for GitHub App user tokens and fine-grained PATs. The Claude App is not granted
  Administration, which is correct for a coding assistant.
- On top of that, this session is scoped to one repository (`mhmadps386/Tel`). The session cannot reach
  repositories outside that list, so even a newly created repo would not be usable until it is added.

Missing permission: **Administration: write** (account-level repo creation) on the Claude GitHub App.

## Least-privilege solution (no bypass)

Granting the App Administration rights would let it create, rename, change visibility of and **delete**
repositories. That is far more than needed. Instead:

1. **The owner creates the repo** (one-time, ~30 s): GitHub → New repository → name `ai-dev-company`,
   **Private**, no template. Leave it empty or initialise it with a README.
2. **Grant the Claude GitHub App access to only that repo**: GitHub → Settings → Applications →
   Installed GitHub Apps → Claude → Configure → Repository access → *Only select repositories* → add
   `ai-dev-company`. The App's existing Contents / Pull requests permissions are enough. No Administration
   is needed.
3. In a Claude Code session, the repo can then be attached (`add_repo mhmadps386/ai-dev-company`, push
   access) and the code moved with history:
   ```sh
   git subtree split --prefix ai-dev-company -b aidc-only
   git push https://github.com/mhmadps386/ai-dev-company.git aidc-only:main
   ```
4. Recommended on the new repo: protect `main` (require a PR and one approval, block force-push),
   enable secret scanning + push protection, keep it private.

Not done, and not recommended: classic PATs with `repo` scope, adding Administration to the App,
or any workaround that creates the repo through another credential.
