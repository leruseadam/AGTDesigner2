# Finding SSH Settings on PythonAnywhere

## Method 1: Account Page (Most Common)
1. Go to **PythonAnywhere.com** and log in
2. Click on your **username** in the top-right corner
3. Select **"Account"** from the dropdown menu
4. Scroll down to find **"SSH keys"** section
5. If you don't see it, try Method 2

## Method 2: Direct URL
1. Go directly to: `https://www.pythonanywhere.com/user/YOUR_USERNAME/ssh_keys/`
2. Replace `YOUR_USERNAME` with your actual PythonAnywhere username
3. This should take you directly to the SSH keys page

## Method 3: Through the Dashboard
1. Go to **PythonAnywhere.com** and log in
2. Look for **"SSH"** in the left sidebar menu
3. Click on it to access SSH settings

## Method 4: If SSH is Not Available
If you can't find SSH settings, it might be because:

### Free Account Limitations
- **Free accounts** on PythonAnywhere may not have SSH access
- You might need to upgrade to a **paid plan** to use SSH

### Alternative: Use Personal Access Token
If SSH is not available, use a GitHub Personal Access Token instead:

1. Go to **GitHub.com** → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. Click **"Generate new token (classic)"**
3. Give it a name like "PythonAnywhere Access"
4. Select these scopes:
   - `repo` (Full control of private repositories)
   - `workflow` (Update GitHub Action workflows)
5. Click **"Generate token"**
6. **Copy the token** (you won't see it again!)

### Using the Token on PythonAnywhere
When Git asks for credentials:
- **Username**: `leruseadam`
- **Password**: Use the personal access token (not your GitHub password)

## Method 5: Check Your Account Type
1. Go to **PythonAnywhere.com** and log in
2. Click on your **username** in the top-right corner
3. Look for your **account type** (Free, Hacker, Developer, etc.)
4. Check if SSH is included in your plan

## Still Can't Find It?
If none of these methods work:
1. Contact PythonAnywhere support
2. Use the Personal Access Token method instead
3. Consider upgrading your account if you need SSH access

## Verification
Once you've set up either SSH or Personal Access Token, test it:
```bash
# For SSH
ssh -T git@github.com

# For Personal Access Token
git clone https://github.com/leruseadam/AGTDesigner.git
# (It will prompt for username and token)
``` 