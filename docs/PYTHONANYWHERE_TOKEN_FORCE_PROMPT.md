# Force Git to Prompt for Token on PythonAnywhere

## Problem
Git isn't prompting for your Personal Access Token on PythonAnywhere.

## Solution: Clear Cached Credentials

### Step 1: Clear Git Credential Cache
On PythonAnywhere, run these commands:

```bash
# Clear any stored credentials
git config --global --unset credential.helper

# Or if using credential store
rm ~/.git-credentials

# Clear any cached credentials in memory
git config --global credential.helper ""
```

### Step 2: Force Git to Ask for Credentials
```bash
# Try to clone or push - this should force a prompt
git clone https://github.com/leruseadam/AGTDesigner.git

# Or if you already have the repo, try:
git push origin main
```

### Step 3: If Still Not Prompting
Try these additional steps:

```bash
# Remove any existing remote
git remote remove origin

# Add remote again
git remote add origin https://github.com/leruseadam/AGTDesigner.git

# Try to fetch - this should prompt for credentials
git fetch origin
```

### Step 4: Manual Credential Entry
If Git still won't prompt, manually set the credentials:

```bash
# Set your username
git config --global user.name "leruseadam"
git config --global user.email "leruseadam@gmail.com"

# Try a command that requires authentication
git ls-remote https://github.com/leruseadam/AGTDesigner.git
```

### Step 5: Alternative - Use Git Credential Manager
If available on PythonAnywhere:

```bash
# Install git credential manager (if available)
git config --global credential.helper manager

# Then try your Git operation
git clone https://github.com/leruseadam/AGTDesigner.git
```

## If Nothing Works

### Method 1: Use URL with Token
Include the token directly in the URL:

```bash
# Replace YOUR_TOKEN with your actual Personal Access Token
git clone https://leruseadam:YOUR_TOKEN@github.com/leruseadam/AGTDesigner.git
```

### Method 2: Environment Variable
Set the token as an environment variable:

```bash
# Set the token (replace YOUR_TOKEN with actual token)
export GITHUB_TOKEN=YOUR_TOKEN

# Then try Git operations
git clone https://github.com/leruseadam/AGTDesigner.git
```

### Method 3: Check PythonAnywhere Console Type
Make sure you're using the **Bash console** on PythonAnywhere, not the Python console.

## Verification Commands

```bash
# Check current Git configuration
git config --list | grep credential

# Check if you can access the repo
curl -u leruseadam:YOUR_TOKEN https://api.github.com/repos/leruseadam/AGTDesigner

# Test Git access
git ls-remote https://github.com/leruseadam/AGTDesigner.git
```

## Common Issues

### Issue: "fatal: Authentication failed"
- Double-check your Personal Access Token
- Make sure the token has the correct permissions (repo access)
- Try regenerating the token

### Issue: "fatal: remote origin already exists"
```bash
git remote remove origin
git remote add origin https://github.com/leruseadam/AGTDesigner.git
```

### Issue: Still using old credentials
```bash
# Clear all Git configuration
git config --global --unset-all credential.helper
git config --global credential.helper ""
``` 