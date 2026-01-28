# 🔒 SECURITY PRE-DEPLOYMENT CHECKLIST

## ✅ Files Currently Protected (.gitignore)

These files are in `.gitignore` and will **NOT** be uploaded:

### 1. Environment Files:
- ✅ `backend/.env` (contains local IPs: 192.168.2.112)
- ✅ `frontend/.env` (contains local IPs: 192.168.2.112)
- ✅ All `.env.*` files

### 2. Sensitive Data:
- ✅ `face_database/` - **Contains facial embeddings** (4 persons registered)
  - This is GDPR/privacy sensitive data
  - Will be lost on Render free tier (no persistence)
  
### 3. Large Files:
- ✅ `video_uploads/*.mp4` - 7 videos currently stored
- ✅ `models/*.pt` - YOLO model files

### 4. Python Cache:
- ✅ `__pycache__/` - Python bytecode

---

## ⚠️ CRITICAL: Manual Verification Before Push

Run this command to verify:
```bash
git status --ignored
```

### Must NOT appear in `git add`:
- [ ] Any `.env` file
- [ ] `face_database/` folder
- [ ] Video files in `video_uploads/`
- [ ] Large model files (*.pt, *.pth)

---

## 🧹 Clean Up Before Deployment

### 1. Remove frontend .env (has local IP):
```bash
# Windows PowerShell
rm frontend\.env

# Or just don't commit it (already in .gitignore)
```

### 2. Verify no secrets in code:
```bash
# Search for potential secrets
git grep -i "password\|secret\|api_key\|token" --untracked
```

### 3. Check for hardcoded IPs:
```bash
git grep -E "\b([0-9]{1,3}\.){3}[0-9]{1,3}\b" backend/ frontend/src/
```

---

## ✅ Safe to Commit

These files are SAFE and should be committed:

### Configuration:
- ✅ `.gitignore` (updated)
- ✅ `requirements.txt` (no secrets)
- ✅ `render.yaml` (deployment config)
- ✅ `.env.example` (template only, no real values)
- ✅ `README_DEPLOYMENT.md` (this file)

### Code:
- ✅ All `.py` files in `backend/`
- ✅ All `.tsx/.ts` files in `frontend/src/`
- ✅ `package.json`, `vite.config.ts`, etc.

### Documentation:
- ✅ `BULK_UPLOAD_GUIDE.md`
- ✅ `DROIDCAM_SETUP.md`
- ✅ `PROJECT_REPORT.md`

---

## 🔐 Sensitive Information Found

### In `frontend/.env`:
```
VITE_DROIDCAM_IP=192.168.2.112  ⚠️ Local network IP
VITE_DROIDCAM_PORT=4747
```
**Status:** Already in `.gitignore` ✅

### In `face_database/`:
- 4 registered persons with facial embeddings
- Metadata includes names and registration dates
**Status:** Already in `.gitignore` ✅

---

## 🚀 Ready to Deploy?

### Final Checklist:
1. [ ] Verified `.env` files are NOT in `git status`
2. [ ] Verified `face_database/` is NOT in `git status`
3. [ ] Removed or excluded local IPs from code
4. [ ] Committed `requirements.txt`, `render.yaml`
5. [ ] Updated `.gitignore`

### Deploy Commands:
```bash
# 1. Add safe files
git add .gitignore
git add backend/requirements.txt
git add render.yaml
git add .env.example
git add README_DEPLOYMENT.md
git add backend/main.py
git add frontend/

# 2. Commit
git commit -m "Add Render deployment configuration"

# 3. Push
git push origin main

# 4. Go to render.com and follow README_DEPLOYMENT.md
```

---

## 📋 Post-Deployment Notes

### On Render (Free Tier):
1. **Face database will be empty** - need to re-register faces
2. **Videos won't persist** - uploaded videos lost on restart
3. **Models auto-download** - YOLO will download on first run

### For Production (Paid Tier):
- Consider external storage (S3, Cloudinary) for videos
- Use MongoDB Atlas for persistent face database
- Add volume mounts for model persistence

---

## 🆘 Emergency: If Secrets Leaked

If you accidentally committed sensitive data:

```bash
# Remove from Git history (DANGEROUS)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch frontend/.env" \
  --prune-empty --tag-name-filter cat -- --all

# Force push (will rewrite history)
git push origin --force --all
```

**Better approach:** Create new API keys/secrets and rotate them.
