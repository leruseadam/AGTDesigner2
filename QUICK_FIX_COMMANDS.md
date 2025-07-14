# Quick Fix Commands - PythonAnywhere Version Mismatch

## 🚀 RECOMMENDED: Upgrade to Python 3.11

### Step 1: Create New Environment
```bash
mkvirtualenv --python=/usr/bin/python3.11 labelmaker-py311
```

### Step 2: Install Requirements
```bash
cd ~/AGTDesigner
pip install --upgrade pip setuptools wheel
pip install -r requirements_pythonanywhere_py313.txt
```

### Step 3: Update Web App
1. Go to PythonAnywhere **Web** tab
2. Click **Edit** on your web app
3. Change Virtual environment to: `/home/adamcordova/.virtualenvs/labelmaker-py311`
4. Click **Save** then **Reload**

---

## 🔧 ALTERNATIVE: Keep Python 3.10

### Step 1: Use Existing Environment
```bash
cd ~/AGTDesigner
source ~/labelmaker-venv/bin/activate
```

### Step 2: Install Compatible Requirements
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements_pythonanywhere_py310.txt
```

### Step 3: Reload Web App
1. Go to PythonAnywhere **Web** tab
2. Click **Reload**

---

## ✅ Verification Commands

```bash
# Check Python version
python --version

# Test key imports
python -c "import pandas, flask, docx; print('✅ All good!')"

# Check virtual environment
echo $VIRTUAL_ENV
```

---

## 🚨 Common Issues

**"No module named 'pandas'"**
```bash
pip install pandas==2.0.3
```

**"Permission denied"**
```bash
chmod -R 755 .
```

**"Virtual environment not found"**
```bash
ls -la ~/.virtualenvs/
```

---

## 📍 Key Points

- **Local**: Python 3.11.0
- **PythonAnywhere**: Python 3.10.12 → **Upgrade to 3.11**
- **Most important**: Update virtual environment path in Web tab
- **Test**: Visit www.agtpricetags.com after changes 