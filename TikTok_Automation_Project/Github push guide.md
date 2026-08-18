# Secure GitHub Push Guide for TikTok Module

## ⚠️ CRITICAL: Security First

**You exposed a GitHub personal access token. Follow these steps:**

### Step 1: Revoke the Exposed Token (DO THIS IMMEDIATELY)

1. Go to: https://github.com/settings/tokens
2. Find the token: `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`
3. Click "Delete" → Confirm
4. Anyone with that token can access your account. It's now invalidated.

### Step 2: Generate a Fresh Personal Access Token

1. Go to: https://github.com/settings/tokens/new
2. Set **Token name**: `jarvis1-automation`
3. Set **Expiration**: 90 days (or your preference)
4. Select **Scopes**:
   - ☑ `repo` (full control of private repositories)
   - ☑ `gist` (create/manage gists)
   - ☑ `workflow` (update GitHub Actions)
5. Click "Generate token"
6. **Copy the token immediately** (you won't see it again)

### Step 3: Store Token Securely (NOT in commits)

**Option A: GitHub CLI (Recommended)**
```bash
gh auth login
# Follow prompts, paste your new token when asked
```

**Option B: Git Credential Manager**
```bash
git config --global credential.helper manager
# Git will prompt for token on first push
```

**Option C: Environment Variable (for scripts)**
```bash
export GH_TOKEN="your_new_token_here"
# Add to your shell profile (.bashrc, .zshrc, etc.)
```

### Step 4: Clone/Navigate to Your Repo

```bash
cd /path/to/jarvis1

# Verify you're in the right repo
git remote -v
# Should show: origin https://github.com/hk7184398-spec/jarvis1.git
```

### Step 5: Add the TikTok Module

```bash
# Create directory structure if it doesn't exist
mkdir -p modules/automation/tiktok

# Copy the files
cp tiktok_automation_enhanced.py modules/automation/tiktok/
cp tiktok_config_example.json modules/automation/tiktok/

# Create __init__.py
touch modules/automation/tiktok/__init__.py
```

### Step 6: Update .gitignore (IMPORTANT!)

```bash
# Add credentials to .gitignore
echo "config/tiktok_config.json" >> .gitignore
echo "modules/automation/tiktok/tiktok_config.json" >> .gitignore
echo ".env" >> .gitignore
echo "tiktok_automation.log" >> .gitignore

# Verify it worked
cat .gitignore | grep tiktok
```

### Step 7: Update requirements.txt

```bash
# Add new dependencies
echo "selenium>=4.0.0" >> requirements.txt
echo "anthropic>=0.25.0" >> requirements.txt

# Verify
tail requirements.txt
```

### Step 8: Stage Files for Commit

```bash
git status  # See what's changed

# Stage the new module
git add modules/automation/tiktok/tiktok_automation_enhanced.py
git add modules/automation/tiktok/__init__.py
git add TIKTOK_INTEGRATION_GUIDE.md
git add GITHUB_PUSH_GUIDE.md
git add requirements.txt
git add .gitignore

# Verify staging
git status
```

### Step 9: Create Commit Message

```bash
git commit -m "feat: Add enhanced TikTok automation with Downloads folder upload

- Direct Downloads folder video picker
- Claude API-powered description & hashtag generation
- Selenium-based upload workflow
- Comprehensive logging and error handling
- Voice command integration ready

Closes: #[issue_number_if_exists]"
```

### Step 10: Push to GitHub

```bash
# For first push with new token
git push origin main

# If prompted for credentials:
# Username: your_github_username
# Password: [paste your new token here]
```

### Step 11: Verify Push

1. Go to: https://github.com/hk7184398-spec/jarvis1
2. You should see the new commit with message starting with "feat: Add enhanced TikTok"
3. Check that `tiktok_config.json` is NOT visible in the repo (should be in .gitignore)

---

## Troubleshooting

### Error: "fatal: Authentication failed"
- Verify your new token is correct
- Check token hasn't expired
- Try: `git config --global credential.helper store` (saves token after first use)

### Error: "Updates were rejected"
- Your local branch is behind remote
- Run: `git pull origin main`
- Then push again: `git push origin main`

### Error: "tiktok_config.json still shows in git"
```bash
# If you accidentally committed it:
git rm --cached tiktok_config.json
git add .gitignore
git commit -m "Remove tiktok_config.json from tracking"
git push origin main
```

### Large file warning
- If video files exist, add to .gitignore:
```bash
echo "*.mp4" >> .gitignore
echo "*.avi" >> .gitignore
```

---

## Checking Token Security

After revoking the old token, verify no other pushes were made:

```bash
# See recent commits
git log --oneline -10

# See who pushed
git log -p --all --grep="token\|credential\|password"

# If suspicious commits found, contact GitHub support
```

---

## Final Checklist

- [ ] Old token revoked from https://github.com/settings/tokens
- [ ] New token generated and stored securely (NOT in code)
- [ ] Using GitHub CLI or Credential Manager for auth
- [ ] .gitignore includes tiktok_config.json and .env
- [ ] TikTok module files copied to `modules/automation/tiktok/`
- [ ] requirements.txt updated
- [ ] Files staged with `git add`
- [ ] Commit message is descriptive
- [ ] Push succeeded with `git push origin main`
- [ ] Verified on GitHub website that new code is visible
- [ ] Verified tiktok_config.json is NOT in repo (hidden by .gitignore)

---

## One-Liner Quick Push (After Setup)

```bash
cd jarvis1 && \
git add modules/automation/tiktok/ requirements.txt .gitignore && \
git commit -m "feat: Add enhanced TikTok automation module" && \
git push origin main
```

---

**Questions?** Check GitHub's security documentation: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure
