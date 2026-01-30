# ERROR_PATTERNS.md - Known Errors and Fixes

*Reference for Kiyomi to quickly diagnose and fix common issues.*

---

## True Podcasts App

### "Generation Failed" / "Connection Error"
**Symptoms:** Red error message, can't generate podcasts
**Cause:** Usually API connection issue
**Fix:**
1. Check `.env.local` has correct API keys
2. Verify Supabase connection
3. Check ElevenLabs API quota
4. Restart the app / redeploy

### Text Not Visible / Light Text
**Symptoms:** Input fields or text appear invisible
**Cause:** Tailwind classes not matching theme
**Fix:**
1. Check for non-existent Tailwind classes
2. Use `text-foreground` instead of custom colors
3. Verify `tailwind.config.ts` has the colors defined
4. Redeploy after fix

### Build Errors - Module Not Found
**Symptoms:** `npm run build` fails with module error
**Cause:** Missing dependency or import
**Fix:**
1. Check import paths
2. Run `npm install`
3. Check `package.json` for missing deps

---

## Next.js Apps (General)

### Hydration Mismatch
**Symptoms:** Console error about hydration
**Cause:** Server/client render difference
**Fix:**
1. Wrap dynamic content in `useEffect`
2. Use `suppressHydrationWarning` sparingly
3. Check for browser-only APIs

### 404 on Refresh
**Symptoms:** Routes work, but 404 on refresh
**Cause:** Static export or routing issue
**Fix:**
1. Check `next.config.js` for `output: 'export'`
2. Verify Vercel settings

### Environment Variables Not Working
**Symptoms:** `undefined` values in app
**Cause:** Env vars not exposed to client
**Fix:**
1. Prefix with `NEXT_PUBLIC_` for client access
2. Check Vercel env settings
3. Redeploy after adding vars

---

## Vercel Deployment

### Deploy Stuck
**Symptoms:** `vercel --prod` hangs
**Cause:** Build taking too long or error
**Fix:**
1. Add `--force` flag
2. Check Vercel dashboard for build logs
3. Cancel and retry

### 500 Error After Deploy
**Symptoms:** Site shows 500 error
**Cause:** Runtime error in server code
**Fix:**
1. Check Vercel function logs: `vercel logs`
2. Look for API route errors
3. Check environment variables are set

---

## Supabase

### Connection Refused
**Symptoms:** Can't connect to database
**Cause:** Wrong URL or service down
**Fix:**
1. Verify `SUPABASE_URL` in env
2. Check Supabase dashboard status
3. Verify API key is correct

### Auth Token Expired
**Symptoms:** 401 errors on authenticated routes
**Cause:** JWT expired or invalid
**Fix:**
1. Clear local storage
2. Re-authenticate
3. Check token refresh logic

---

## Streamlit Apps

### Module Import Error
**Symptoms:** App won't start
**Cause:** Missing dependency
**Fix:**
1. Add to `requirements.txt`
2. Push to git for Streamlit Cloud redeploy

### Memory Error
**Symptoms:** App crashes on large operations
**Cause:** Resource limits
**Fix:**
1. Process data in chunks
2. Use `st.cache_data` for caching
3. Reduce data size

---

## Quick Diagnosis Flow

1. **Read the error message carefully**
2. **Check which project/URL**
3. **Look for patterns above**
4. **If API error → check env vars**
5. **If build error → check code changes**
6. **If deploy error → check Vercel logs**
7. **When in doubt → redeploy with `--force`**

---

*Add new patterns as they're discovered!*
*Last updated: 2026-01-28*
