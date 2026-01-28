# 🚀 Quick Deployment Guide - Aegis Vision to Render.com

## ✅ Security Status: VERIFIED SAFE TO DEPLOY

### Protected Files (Won't be committed):
- ✅ `.env` files (local IPs protected)
- ✅ `face_database/` (4 registered persons - privacy protected)
- ✅ `video_uploads/` (7 videos - won't upload)
- ✅ `__pycache__/` (Python cache)

---

## 📦 Step 1: Push to GitHub (5 minutes)

```powershell
# Navigate to project
cd "c:\Users\BEST BUY COMPUTERS\Desktop\Pakistan-AI-Challenge-2026\Aegis-Vision"

# Stage safe files
git add .gitignore
git add backend/requirements.txt
git add backend/main.py
git add frontend/
git add render.yaml
git add *.md

# Commit
git commit -m "Add Render deployment configuration"

# Push
git push origin main
```

---

## 🌐 Step 2: Deploy on Render.com (10 minutes)

### A. Create Account
1. Go to **https://render.com**
2. Click "Get Started for Free"
3. Sign up with GitHub (easiest)

### B. Deploy Backend API

1. Click **"New +"** → **"Web Service"**
2. Connect repository: `Esh90/Aegis-Vision`
3. Fill in:
   ```
   Name: aegis-vision-backend
   Region: Frankfurt
   Branch: main
   Root Directory: backend
   Runtime: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
   Instance Type: Free
   ```
4. Environment Variables (click "Add Environment Variable"):
   ```
   PYTHON_VERSION = 3.11.0
   CONFIDENCE_THRESHOLD = 0.4
   ```
5. Click **"Create Web Service"**
6. ⏰ Wait 5-10 minutes for build
7. **📋 COPY YOUR BACKEND URL** (e.g., `https://aegis-vision-backend.onrender.com`)

### C. Deploy Frontend

1. Click **"New +"** → **"Static Site"**
2. Connect repository: `Esh90/Aegis-Vision`
3. Fill in:
   ```
   Name: aegis-vision-frontend
   Branch: main
   Root Directory: frontend
   Build Command: npm install && npm run build
   Publish Directory: dist
   ```
4. Environment Variable:
   ```
   VITE_API_URL = [PASTE YOUR BACKEND URL FROM STEP B.7]
   ```
   Example: `https://aegis-vision-backend.onrender.com`
   
5. Click **"Create Static Site"**
6. ⏰ Wait 3-5 minutes
7. **📋 COPY YOUR FRONTEND URL** (e.g., `https://aegis-vision-frontend.onrender.com`)

### D. Update Backend CORS

1. Go back to backend service in Render
2. Click **"Environment"** tab
3. Add new variable:
   ```
   CORS_ORIGINS = [PASTE YOUR FRONTEND URL FROM STEP C.7]
   ```
   Example: `https://aegis-vision-frontend.onrender.com`
4. Click **"Save Changes"**
5. Backend will automatically redeploy (2-3 minutes)

---

## 🎉 Step 3: Test Your Deployment

1. Visit your frontend URL
2. Test features:
   - ✅ Upload a video
   - ✅ See object detection
   - ✅ Register a face
   - ✅ Test face recognition

---

## 📝 Step 4: Portfolio Links

Share these in your portfolio/CV:

- **🌐 Live Demo:** `https://aegis-vision-frontend.onrender.com`
- **📚 API Docs:** `https://aegis-vision-backend.onrender.com/docs`
- **💻 GitHub:** `https://github.com/Esh90/Aegis-Vision`

---

## ⚠️ Important Notes

### Free Tier Limitations:
1. **Services sleep after 15 min** - First load takes 30-60 seconds
2. **No persistent storage** - Face database resets on redeploy
3. **512MB RAM limit** - Can process small to medium videos

### Tips:
- Keep service awake: Use [cron-job.org](https://cron-job.org) to ping every 14 min
- For demo: Pre-load by visiting site before showing to judges
- Models auto-download on first run (may take extra time)

---

## 🐛 Troubleshooting

**Backend build fails?**
- Check logs in Render dashboard
- Verify `requirements.txt` is committed
- May need to reduce package versions

**Frontend can't connect?**
- Double-check `VITE_API_URL` matches backend URL
- Verify CORS_ORIGINS in backend matches frontend URL
- Look at browser console (F12) for errors

**Site is slow?**
- Normal on first request (service waking up)
- Subsequent requests are fast
- Keep alive with cron job

---

## 📞 Need Help?

1. Check [README_DEPLOYMENT.md](README_DEPLOYMENT.md) for detailed guide
2. Check [SECURITY_CHECKLIST.md](SECURITY_CHECKLIST.md) for security details
3. Render Docs: https://render.com/docs
4. GitHub Issues: Open issue in your repo

---

## ⏱️ Total Time: ~20 minutes
- Pushing to GitHub: 5 min
- Deploying backend: 10 min
- Deploying frontend: 5 min
- Testing: Variable

**Good luck with your portfolio! 🎯**
