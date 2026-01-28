# 📱 DroidCam Setup Guide for Aegis-Vision

## 🔴 **Current Issue: DroidCam Classic doesn't support USB on Android**

You have **DroidCam Webcam Classic** which only supports WiFi on tablets. Here are your options:

---

## ✅ **Option 1: Use WiFi (FREE - Works Now!)**

### Setup:
1. **Connect both devices to same WiFi network**
2. Open **DroidCam** app on tablet
3. Tap **WiFi** button
4. Note the IP address shown (e.g., `192.168.1.15`)
5. Note the port (usually `4747`)

### In Aegis-Vision:
1. Select **"DroidCam - Enter IP Below"** from dropdown
2. Enter IP: `192.168.1.15`
3. Port: `4747`
4. Click **"Connect DroidCam"**

### 🔒 **Pre-configure IP in .env (Secure):**
```bash
# Edit: frontend/.env
VITE_DROIDCAM_IP=192.168.1.15
VITE_DROIDCAM_PORT=4747
```
Then restart frontend: `npm run dev`

---

## 💰 **Option 2: Upgrade to DroidCam X (Paid - $5.49)**

**Features:**
- ✅ USB support
- ✅ Higher resolution (1080p)
- ✅ No ads
- ✅ Shows as "Camera 1" in Windows

**Download:** https://play.google.com/store/apps/details?id=com.dev47apps.droidcamx

**After Installation:**
1. Install **DroidCam Client** on Windows
2. Connect tablet via USB
3. Open DroidCam Client on PC
4. Select USB connection
5. In Aegis: Select "Camera 1 - External USB Camera"

---

## 🆓 **Option 3: IP Webcam (FREE Alternative with USB)**

**Download:** https://play.google.com/store/apps/details?id=com.pas.webcam

**Features:**
- ✅ Completely free
- ✅ WiFi support (like DroidCam)
- ✅ USB tethering option
- ✅ Multiple video formats

**WiFi Setup:**
1. Open IP Webcam app
2. Scroll down and tap **"Start Server"**
3. Note the URL shown (e.g., `http://192.168.1.15:8080`)
4. In Aegis: Select "DroidCam - Enter IP Below"
5. Enter IP: `192.168.1.15`
6. Port: `8080`
7. Click "Connect DroidCam"

**URL Format:** `http://192.168.1.15:8080/video`

---

## 🎯 **Recommended: WiFi Method**

**Why WiFi is better for your use case:**
- ✅ No cables - more flexibility
- ✅ Can position tablet anywhere in room
- ✅ No USB driver issues
- ✅ Works immediately with current setup
- ✅ Competition-ready (judges will see it as professional)

**For competition demo:**
- Set static IP on tablet WiFi settings
- Add IP to `.env` file for instant connection
- One-click start!

---

## 🔧 **Troubleshooting WiFi Connection**

### "Cannot connect to DroidCam"
1. Check both devices on **same WiFi network**
2. Try pinging tablet from PC: `ping 192.168.1.15`
3. Disable firewall temporarily
4. Check router allows device-to-device communication
5. Try different port (e.g., `4747`, `8080`)

### "Video feed is slow"
1. Use 5GHz WiFi if available
2. Reduce resolution in DroidCam app settings
3. Move closer to WiFi router
4. Close other apps on tablet

### "IP keeps changing"
1. Set **Static IP** on tablet:
   - Settings → WiFi → Your Network → Advanced
   - Set IP: `192.168.1.100` (example)
   - Gateway: Your router IP
   - DNS: `8.8.8.8`

---

## 📋 **Quick Test Checklist**

✅ Tablet and laptop on same WiFi  
✅ DroidCam app shows IP address  
✅ Can ping tablet from laptop  
✅ IP entered correctly in Aegis  
✅ Port matches (4747 or 8080)  
✅ Firewall allows connection  

---

## 🏆 **Competition Day Setup**

**Pre-configure everything:**
```bash
# frontend/.env
VITE_DROIDCAM_IP=192.168.1.100
VITE_DROIDCAM_PORT=4747
```

**Morning of competition:**
1. Connect tablet to hotspot/venue WiFi
2. Verify IP matches `.env` (or update it)
3. Restart frontend once
4. Click "Connect DroidCam" → Instant connection!

---

## 💡 **Pro Tip:**

For the competition, create a **mobile hotspot from your laptop** and connect the tablet to it. This way:
- You control the network
- IP never changes
- No venue WiFi issues
- Ultra-reliable connection

**Hotspot Setup:**
1. Windows Settings → Network → Mobile Hotspot
2. Turn ON
3. Connect tablet to your laptop's hotspot
4. Note tablet's IP (will be like `192.168.137.xxx`)
5. Add to `.env`

This is the **MOST RELIABLE** method for competition day! 🎯
