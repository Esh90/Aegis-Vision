# 📦 Bulk Watchlist Upload Guide

## Quick Start

Upload multiple suspects to watchlist at once using **Excel + ZIP**.

---

## 📋 Step 1: Create Excel File

Use the provided `watchlist_template.xlsx` or create your own with these columns:

| Column | Required | Values | Example |
|--------|----------|--------|---------|
| **name** | ✅ Yes | Person's name | John Doe |
| **image_filename** | ✅ Yes | Filename in ZIP | john_doe.jpg |
| **risk_level** | ❌ Optional | LOW, MEDIUM, HIGH | HIGH |
| **notes** | ❌ Optional | Description | Armed robbery suspect |

**Example Excel:**
```
name          | image_filename    | risk_level | notes
--------------|-------------------|------------|------------------------
John Doe      | john_doe.jpg      | HIGH       | Armed robbery suspect
Jane Smith    | jane_smith.jpg    | MEDIUM     | Fraud investigation
Ahmed Khan    | ahmed.png         | LOW        | Person of interest
```

---

## 📁 Step 2: Create ZIP with Images

1. Collect all images (JPG, PNG, BMP)
2. Make sure filenames **match** the `image_filename` column
3. Create a ZIP file containing all images

**ZIP Structure:**
```
suspects_images.zip
├── john_doe.jpg
├── jane_smith.jpg
└── ahmed.png
```

**Important:**
- ✅ Images can be in subfolders (will search recursively)
- ✅ Filename matching is case-insensitive
- ✅ Supported formats: .jpg, .jpeg, .png, .bmp
- ❌ Make sure face is clearly visible (frontal view preferred)

---

## 🚀 Step 3: Upload via API

### Using cURL:
```bash
curl -X POST http://localhost:8000/api/watchlist/bulk-upload \
  -F "excel_file=@watchlist.xlsx" \
  -F "images_zip=@images.zip"
```

### Using Frontend (Coming Soon):
Dashboard will have a "Bulk Upload" button with drag-and-drop interface.

---

## 📊 Response Format

```json
{
  "success": true,
  "total": 10,
  "processed": 8,
  "failed": 2,
  "entries": [
    {
      "index": 1,
      "name": "John Doe",
      "image_filename": "john_doe.jpg",
      "success": true,
      "person_id": "person_1738012345678_0",
      "error": null
    },
    {
      "index": 2,
      "name": "Jane Smith",
      "image_filename": "jane_smith.jpg",
      "success": false,
      "error": "No face detected",
      "person_id": null
    }
  ]
}
```

---

## ⚠️ Common Issues

### "Image not found in ZIP"
- Check spelling of filenames
- Make sure ZIP contains the image
- Filenames are case-insensitive but must match

### "No face detected"
- Use frontal face photos
- Ensure good lighting
- Face should be at least 50x50 pixels
- Avoid sunglasses, masks, extreme angles

### "Failed to extract embedding"
- Image quality too low
- Face too blurry
- Multiple faces in photo (will use largest)

---

## 🎯 Best Practices

1. **Image Quality:**
   - Resolution: At least 640x480
   - Face size: Minimum 100x100 pixels
   - Lighting: Well-lit, avoid extreme shadows
   - Angle: Frontal view preferred

2. **Excel Formatting:**
   - Don't use special characters in names
   - Keep notes concise
   - Use consistent risk levels (LOW/MEDIUM/HIGH)

3. **Testing:**
   - Start with 2-3 entries to test
   - Verify successful uploads before bulk processing
   - Check backend logs for detailed errors

---

## 🔧 Technical Details

- **Processing**: Sequential (one at a time)
- **Speed**: ~2-3 seconds per person
- **Limit**: No hard limit, but 100+ may take several minutes
- **Same preprocessing as live feed**: Enhancement, face detection, super-resolution, embedding extraction
- **Persistence**: All data saved to disk immediately

---

## 📝 Template Download

Use the provided `watchlist_template.xlsx` in the `backend/` folder as a starting point.

Edit it in Excel/Google Sheets, then upload with your ZIP of images!
