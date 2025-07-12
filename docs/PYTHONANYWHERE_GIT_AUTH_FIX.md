# Fixing Git Authentication on PythonAnywhere

## Problem
You're getting a 403 error when trying to access your GitHub repository:
```
Permission to leruseadam/AGTDesigner.git denied to leruseadam.
fatal: unable to access 'https://github.com/leruseadam/AGTDesigner.git/': The requested URL returned error: 403
```

## Solution: Use SSH Authentication

### Step 1: Add SSH Key to GitHub
1. Copy your SSH public key:
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDXQ/NRzexq4Aq2gqws5iIwNuNxKXbFHggVhKbF6IDfI leruseadam@gmail.com
```

2. Go to GitHub.com → Settings → SSH and GPG keys → New SSH key
3. Paste the key and save it

### Step 2: Add SSH Key to PythonAnywhere
1. Go to PythonAnywhere.com and log in
2. Go to the 'Account' page
3. Scroll down to 'SSH keys' section
4. Add the same SSH public key
5. Save the key

### Step 3: Use SSH URL Instead of HTTPS
Instead of using HTTPS URLs, use SSH URLs:

**For new clones:**
```bash
git clone git@github.com:leruseadam/AGTDesigner.git
```

**For existing repositories:**
```bash
git remote set-url origin git@github.com:leruseadam/AGTDesigner.git
```

### Step 4: Test the Connection
```bash
ssh -T git@github.com
```

You should see: "Hi leruseadam! You've successfully authenticated..."

## Alternative: Personal Access Token (if SSH doesn't work)

If SSH doesn't work, you can use a Personal Access Token:

1. Go to GitHub.com → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with 'repo' permissions
3. Use the token as your password when Git prompts for credentials

## Common Issues and Solutions

### Issue: SSH key not working
- Make sure the key is added to both GitHub and PythonAnywhere
- Check that the key format is correct
- Try regenerating the key if needed

### Issue: Still getting 403 errors
- Clear any cached credentials: `git config --global --unset credential.helper`
- Make sure you're using the SSH URL, not HTTPS
- Check that your GitHub account has access to the repository

### Issue: Permission denied
- Verify your SSH key is properly added to GitHub
- Check that the repository exists and you have access to it
- Ensure your PythonAnywhere account has SSH access enabled

## Verification Commands

```bash
# Check current remote URL
git remote -v

# Test SSH connection to GitHub
ssh -T git@github.com

# Check Git configuration
git config --list | grep -E "(user\.name|user\.email|credential)"
``` 