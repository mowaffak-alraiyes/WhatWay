# 🧪 Quick Test Checklist

## **Core Functionality Tests**

### **1. Data Loading & Caching** ✅
- [ ] Switching categories loads correct dataset without refetching
- [ ] Pressing "Reset Chat" clears cache and forces fresh fetch
- [ ] GitHub URL fallback to local files works if GitHub is down

### **2. Category Selector** ✅
- [ ] Radio buttons stay highlighted across reruns
- [ ] Switching categories loads correct ZIPs/Languages for that dataset
- [ ] No exceptions if one source is down

### **3. Search & Ranking** ✅
- [ ] "dental 60629" → top 3 dental clinics in that ZIP only (auto-detected)
- [ ] "ESL monday" → ESL programs available on Monday (auto-detected)
- [ ] "legal help mon" → legal services available on Monday (auto-detected)
- [ ] "clinic tue-thu" → clinics open Tuesday through Thursday (auto-detected)
- [ ] "legal" in Resettlement/Legal/Shelter → legal/immigration items only
- [ ] "ESL Uptown" in Education → ESL/English items with "Uptown" signals
- [ ] Healthcare ignores "clinic" filler word in queries
- [ ] ZIP codes, services, and days in search queries automatically apply filtering
- [ ] Manual sidebar filters still work and can override auto-detected values

### **4. "More" Pagination** ✅
- [ ] "dental 60629" → 3 items → user types "more" → next 3 (no repeats)
- [ ] No new items on "more" shows trusted resources block
- [ ] Non-"more" queries don't exclude prior items

### **5. Pin Functionality** ✅
- [ ] One click pins item
- [ ] One more click unpins item
- [ ] Sidebar updates immediately
- [ ] Chat history stays intact
- [ ] No interruptions to other functions

### **6. Chat Flow** ✅
- [ ] User message appears immediately after input
- [ ] AI response follows below user message
- [ ] Next user prompt goes below AI response
- [ ] Pattern: user → AI → user → AI

### **7. Misspelling Detection** ✅
- [ ] "dentel 60629" triggers "Did you mean dental?" suggestion
- [ ] "Yes" response runs corrected search
- [ ] "No" response asks clarifying follow-up question
- [ ] Waiting gate respected before treating input as new search

### **8. Filters & Reset** ✅
- [ ] ZIP, Language, Service, and Day filters built from loaded dataset
- [ ] Service filter shows category-specific options (dental, ESL, legal, etc.)
- [ ] Day filter only shows days when services are actually open (based on hours data)
- [ ] Day filter hidden if no hours data available in dataset
- [ ] Reset clears chat, pins, shown IDs, and cache
- [ ] No deprecation warnings
- [ ] Scroll to Latest button jumps to bottom

### **9. Smart Day Parsing** ✅
- [ ] "Mon" automatically recognized as "Monday"
- [ ] "Mon-Thu" parsed as Monday, Tuesday, Wednesday, Thursday
- [ ] "Mon, Wed, Fri" parsed as individual days
- [ ] Handles day ranges that wrap around (e.g., "Fri-Mon")
- [ ] Supports both abbreviated and full day names
- [ ] No duplicate days in filter options

### **9. UI/UX** ✅
- [ ] Category pills stay highlighted
- [ ] Full details printed inline (no expanders)
- [ ] Friendly, conversational assistant text
- [ ] Proactive follow-up suggestions
- [ ] Auto-scroll after responses

### **10. Fallback Handling** ✅
- [ ] General questions get friendly fallback
- [ ] No results shows FindHelp/211/HRSA links
- [ ] Never fabricates providers or claims
- [ ] Always invites productive next steps

### **11. QR Code Generation** ✅
- [ ] QR code displayed in sidebar for easy app access
- [ ] Uses APP_PUBLIC_URL from secrets if available
- [ ] Falls back to LOCAL_URL for local network access
- [ ] QR code can be downloaded as PNG file
- [ ] App continues working if QR generation fails
- [ ] Shows appropriate status messages (public vs local)

## **Test Commands to Run**

```bash
# Test basic functionality
streamlit run chat_llama.py

# Test specific scenarios:
1. Type "dental 60629" → should show 3 dental clinics in 60629 area (auto-detected ZIP)
2. Type "ESL monday" → should show ESL programs available on Monday (auto-detected day)
3. Type "legal help mon" → should show legal services available on Monday (auto-detected day)
4. Type "clinic tue-thu" → should show clinics open Tuesday through Thursday (auto-detected day range)
5. Type "more" → should show next 3 (no repeats)
6. Type "legal" in Resettlement category → should show legal items only
7. Type "dentel" → should suggest "dental" correction
8. Click pin button → should pin/unpin with one click
9. Switch categories → should load new dataset and filters
10. Press Reset Chat → should clear everything and refresh cache
11. Test Scroll to Latest → should jump to bottom
12. Type "ESL 60637" → should show ESL programs in 60637 area
13. Set sidebar filters, then search with different terms → should use sidebar filters
14. Test service filter dropdown → should show category-specific options
15. Test day filter dropdown → should only show days when services are actually open
16. Test with dataset that has no hours data → day filter should be hidden
17. Test day range parsing: "Mon-Thu", "Mon, Wed, Fri", "Fri-Mon"
18. Test QR code generation → should display QR code in sidebar
19. Test QR code download → should download PNG file
20. Test QR code with/without APP_PUBLIC_URL in secrets
```

## **Expected Behavior**

- **Zero hallucinations** - Only shows items from parsed TXT files
- **Robust parsing** - Handles missing emojis and various formats
- **Friendly AI** - Conversational but grounded in dataset
- **Instant feedback** - User messages appear immediately
- **Smart caching** - No unnecessary refetches
- **Clean state** - Reset clears everything properly
