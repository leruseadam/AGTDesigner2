# PythonAnywhere Fix Instructions

## Problem Summary
PythonAnywhere is experiencing two issues:
1. **Default file loading** - Keeps defaulting to older files
2. **Manual upload** - Doesn't work due to Flask context errors

## Root Cause
The PythonAnywhere deployment is running an old version of the code that has Flask context errors in the background processing. The fixes are already in the GitHub repository but need to be deployed to PythonAnywhere.

## Solution Steps

### Step 1: Update PythonAnywhere Code
1. **Open PythonAnywhere Console:**
   - Log into your PythonAnywhere account
   - Go to the "Consoles" tab
   - Open a new Bash console

2. **Navigate to your project:**
   ```bash
   cd /home/adamcordova/AGTDesigner
   ```

3. **Pull the latest fixes:**
   ```bash
   git pull origin main
   ```

4. **Verify the fixes are deployed:**
   ```bash
   git log --oneline -3
   ```
   You should see: `3ed6501 Fix PythonAnywhere file upload - resolve Flask context errors in background processing`

5. **Check that the Flask context fixes are in place:**
   ```bash
   grep -n "has_request_context" app.py
   ```
   This should show several lines with the fix.

### Step 2: Reload the Web App
1. **Go to the Web tab** in your PythonAnywhere dashboard
2. **Click the "Reload" button** to restart your web app
3. **Wait for the reload to complete** (status should turn green)

### Step 3: Test the Fixes
1. **Test default file loading:**
   - Visit your PythonAnywhere URL
   - Check if the most recent file is loaded automatically
   - The logs should show the correct file being found

2. **Test manual upload:**
   - Try uploading a new file
   - The upload should work without Flask context errors
   - Check the upload status - should show "ready" instead of errors

### Step 4: Verify Deployment
Run the diagnostic script to verify everything is working:

```bash
cd /home/adamcordova/AGTDesigner
python3 check_pythonanywhere_deployment.py
```

## Expected Results After Fix

### ✅ Default File Loading Should Work:
- Application will automatically load the most recent AGT file on startup
- Logs will show: `"Loading default file on startup: [most recent file path]"`
- Status API will show data is loaded

### ✅ Manual Upload Should Work:
- File uploads will process successfully
- No more "Working outside of request context" errors
- Upload status will show "ready" instead of errors
- Available tags will update correctly

## Troubleshooting

### If the fixes don't deploy:
1. **Check git status:**
   ```bash
   git status
   git log --oneline -5
   ```

2. **Force pull if needed:**
   ```bash
   git fetch origin
   git reset --hard origin/main
   ```

3. **Clear any cached files:**
   ```bash
   find . -name "*.pyc" -delete
   find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
   ```

### If the web app won't reload:
1. **Check error logs** in the Web tab
2. **Try a hard reload** by stopping and starting the web app
3. **Check file permissions:**
   ```bash
   chmod -R 755 /home/adamcordova/AGTDesigner
   ```

### If uploads still don't work:
1. **Check the error logs** in the Web tab
2. **Verify the Flask context fixes are in place:**
   ```bash
   grep -A 5 -B 5 "has_request_context" app.py
   ```

## What the Fixes Include

### Flask Context Error Fixes:
- ✅ Protected session access with `has_request_context()` checks
- ✅ Added fallback values for background processing
- ✅ Fixed `get_session_cache_key()` function for background threads
- ✅ Proper error handling and cleanup

### Default File Loading Improvements:
- ✅ Enhanced PythonAnywhere detection
- ✅ Multiple search locations for AGT files
- ✅ Most recent file selection based on modification time
- ✅ Comprehensive logging for debugging

## Contact
If you continue to have issues after following these steps, please check the error logs in the PythonAnywhere Web tab and provide the specific error messages. 