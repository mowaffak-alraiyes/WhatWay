# GitHub .txt Files as Source of Truth

## How It Works

The app **always fetches from GitHub .txt files first** as the source of truth:

1. **GitHub URLs** (primary source):
   - `https://raw.githubusercontent.com/mowaffak-alraiyes/refugee-resources/main/resources/healthcare.txt`
   - `https://raw.githubusercontent.com/mowaffak-alraiyes/refugee-resources/main/resources/education.txt`
   - `https://raw.githubusercontent.com/mowaffak-alraiyes/refugee-resources/main/resources/ResettlementLegalShelterBasicNeeds.txt`

2. **Data Flow**:
   ```
   GitHub .txt files → data_loader.py → Parse & Normalize → JSON files → chat_llama.py
   ```

3. **Automatic Updates**:
   - Cache expires after 5 minutes
   - When cache expires, fetches fresh from GitHub
   - JSON files are automatically regenerated from GitHub .txt files
   - If .txt files change on GitHub, JSON will update on next load

## Ensuring Fresh Data

The `data_loader.py` function:
- ✅ Always tries GitHub URLs first
- ✅ Falls back to local files only if GitHub fails
- ✅ Regenerates JSON files from fresh .txt data
- ✅ Cache is short (5 minutes) to catch updates quickly

## Manual Refresh

To force refresh from GitHub:
1. Use the Admin page: Click "🔄 Refresh" for any category
2. Or clear cache: Admin page → "🗑️ Clear All Caches"

## Benefits

- ✅ **Single source of truth**: GitHub .txt files
- ✅ **Automatic sync**: JSON updates when .txt files change
- ✅ **Flexible**: Edit .txt files on GitHub, changes propagate automatically
- ✅ **Fast**: JSON files provide fast loading, but always based on GitHub data


