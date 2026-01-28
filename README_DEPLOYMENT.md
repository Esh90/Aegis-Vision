# 🚀 Aegis-Vision Deployment Guide (Render.com)

## 📋 Pre-Deployment Checklist

### ✅ Security Verification
- [x] `.gitignore` includes `.env` files
- [x] `.gitignore` includes `face_database/` (personal data)
- [x] No API keys or secrets in code
- [x] DroidCam IP addresses not hardcoded
- [x] requirements.txt created

### ⚠️ Files to NEVER Commit:
- `.env` (contains local IPs)
- `face_database/` (contains facial embeddings - GDPR sensitive)
- `*.pt` model files (too large for Git)
- `video_uploads/` (can be very large)
- `__pycache__/` (Python cache)

---

## 🔧 Step-by-Step Deployment

### Step 1: Prepare Your Repository

1. **Verify .gitignore is working:**
```bash
git status
```
Make sure these are NOT listed:
- `.env`
- `face_database/`
- Large model files

2. **Commit and push to GitHub:**
```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

---

### Step 2: Create Render Account

1. Go to [https://render.com](https://render.com)
2. Click **"Get Started for Free"**
3. Sign up with GitHub (recommended - easier deployment)

---

### Step 3: Deploy Backend

1. **In Render Dashboard:**
   - Click **"New +"** → **"Web Service"**
   
2. **Connect Repository:**
   - Select **"Build and deploy from a Git repository"**
   - Find and select: `Esh90/Aegis-Vision`
   
3. **Configure Backend Service:**
   ```
   Name: aegis-vision-backend
   Region: Frankfurt (closest to Pakistan)
   Branch: main
   Root Directory: backend
   Runtime: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

4. **Instance Type:**
   - Select **"Free"** (512MB RAM, 0.1 CPU)

5. **Environment Variables:**
   Add these in the "Environment" section:
   ```
   PYTHON_VERSION=3.11.0
   CONFIDENCE_THRESHOLD=0.4
   ```

6. Click **"Create Web Service"**

7. **Wait 5-10 minutes** for build to complete

8. **Copy the backend URL** (e.g., `https://aegis-vision-backend.onrender.com`)

---

### Step 4: Deploy Frontend

1. **In Render Dashboard:**
   - Click **"New +"** → **"Static Site"**

2. **Connect Repository:**
   - Select: `Esh90/Aegis-Vision`

3. **Configure Frontend:**
   ```
   Name: aegis-vision-frontend
   Branch: main
   Root Directory: frontend
   Build Command: npm install && npm run build
   Publish Directory: dist
   ```

4. **Environment Variables:**
   Add in "Environment" section:
   ```
   VITE_API_URL=https://aegis-vision-backend.onrender.com
   ```
   ⚠️ **Replace with your actual backend URL from Step 3**

5. Click **"Create Static Site"**

6. **Wait 3-5 minutes** for build

---

### Step 5: Update CORS (Backend)

The backend needs to allow requests from your frontend domain.

1. Go to your backend service in Render
2. Go to **"Environment"** tab
3. Add:
   ```
   CORS_ORIGINS=https://aegis-vision-frontend.onrender.com
   ```
   ⚠️ **Replace with your actual frontend URL**

4. Click **"Save Changes"** (backend will redeploy)

---

### Step 6: Test Your Deployment

1. **Visit your frontend URL** (e.g., `https://aegis-vision-frontend.onrender.com`)

2. **Test features:**
   - ✅ Dashboard loads
   - ✅ Can upload video files
   - ✅ Object detection works
   - ✅ Face recognition works (after registering faces)

---

## 🎯 Important Notes

### ⚠️ Limitations of Free Tier:

1. **Services sleep after 15 min of inactivity**
   - First request will be slow (30-60 seconds)
   - Subsequent requests are fast

2. **No persistent storage**
   - Face database will reset on redeploy
   - Video uploads are lost on restart
   - Consider upgrading to paid tier for persistence

3. **Memory limits (512MB)**
   - Can only process smaller videos
   - May need to optimize model loading

### 💡 Tips:

- **Keep service awake:** Use [cron-job.org](https://cron-job.org) to ping your API every 14 minutes
- **Model optimization:** YOLO11n is already lightweight, but consider quantization for production
- **Database:** For persistent face database, use external DB (e.g., MongoDB Atlas free tier)

---

## 🔗 Portfolio Links

After deployment, share these links:

- **Live Demo:** `https://aegis-vision-frontend.onrender.com`
- **API Docs:** `https://aegis-vision-backend.onrender.com/docs`
- **GitHub Repo:** `https://github.com/Esh90/Aegis-Vision`

---

## 🐛 Troubleshooting

### Backend won't start:
- Check build logs in Render dashboard
- Verify `requirements.txt` is correct
- Check memory usage (512MB limit)

### Frontend can't connect to backend:
- Verify `VITE_API_URL` in frontend environment variables
- Check CORS settings in backend
- Look at browser console for errors

### Models not loading:
- YOLO will auto-download on first run (may timeout on free tier)
- Consider committing `yolo11n.pt` to repo (if under 100MB)

---

## 📞 Support

For issues, check:
- Render Status: [https://status.render.com](https://status.render.com)
- Render Docs: [https://render.com/docs](https://render.com/docs)
