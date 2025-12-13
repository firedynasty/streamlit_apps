# Vercel Deployment with Environment Variables

How to deploy a React app with serverless API functions to Vercel.

---

## Project Structure Required

```
your-project/
├── api/
│   └── chat.js          # Serverless function (auto-detected by Vercel)
├── src/
│   └── App.js           # React frontend
├── public/
├── package.json
└── vercel.json          # Routing config
```

---

## vercel.json Configuration

### Recommended (Modern - Auto-detect)

```json
{
  "rewrites": [
    { "source": "/api/:path*", "destination": "/api/:path*" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

**How it works:**
- Vercel auto-detects Create React App, runs `npm run build`
- Vercel auto-detects `api/` folder as serverless functions
- First rewrite: `/api/*` goes to serverless functions
- Second rewrite: Everything else goes to React SPA

### Legacy (Explicit Builds)

```json
{
  "version": 2,
  "builds": [
    {
      "src": "package.json",
      "use": "@vercel/static-build",
      "config": { "distDir": "build" }
    },
    {
      "src": "api/chat.js",
      "use": "@vercel/node"
    }
  ],
  "routes": [
    { "src": "/api/chat", "dest": "/api/chat.js" },
    { "src": "/(.*)", "dest": "/index.html" }
  ]
}
```

**Note:** Using `builds` triggers legacy mode and may produce longer URLs.

---

## Environment Variables

### In Vercel Dashboard

1. Go to **vercel.com** → Your Project → **Settings** → **Environment Variables**
2. Add your variables:

| Key | Value | Environment |
|-----|-------|-------------|
| `OPENAI_API_KEY` | `sk-proj-...` | Production, Preview, Development |
| `ACCESS_CODE` | `your-secret` | Production, Preview, Development |

3. Click **Save**
4. **Redeploy** (variables are baked in at build time)

### Via CLI

```bash
# Add variables interactively
vercel env add OPENAI_API_KEY
vercel env add ACCESS_CODE

# Or pull existing to .env.local for local dev
vercel env pull
```

### Variable Naming Rules

| Prefix | Visibility | Use For |
|--------|------------|---------|
| No prefix | Server-side only | API keys, secrets |
| `REACT_APP_*` | Client-side (exposed!) | Non-secret config |

**Important:** Never use `REACT_APP_` for secrets - they get bundled into JavaScript!

### Accessing in Code

```javascript
// In api/chat.js (server-side)
const apiKey = process.env.OPENAI_API_KEY;      // Works
const code = process.env.ACCESS_CODE;            // Works

// In React components (client-side)
const publicValue = process.env.REACT_APP_PUBLIC_URL;  // Works (but exposed!)
const apiKey = process.env.OPENAI_API_KEY;             // undefined (correct!)
```

---

## Deployment Commands

### Deploy to Production

```bash
cd your-project
vercel --prod
```

### Expected Output

```
Vercel CLI 49.x.x
Building...
✅ Production: https://your-project.vercel.app [33s]
```

### Other Commands

```bash
vercel              # Deploy to preview
vercel --prod       # Deploy to production
vercel dev          # Run locally with serverless functions
vercel logs         # View function logs
vercel env ls       # List environment variables
```

---

## package.json Requirements

```json
{
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "vercel-build": "react-scripts build"
  }
}
```

The `vercel-build` script is required when using `@vercel/static-build`.

---

## Troubleshooting

### 404 on /api/chat

**Problem:** API route not found

**Solutions:**
1. Ensure `api/chat.js` is in project root (not `src/api/`)
2. Check vercel.json has API rewrite BEFORE catch-all:
   ```json
   { "source": "/api/:path*", "destination": "/api/:path*" },
   { "source": "/(.*)", "destination": "/index.html" }
   ```
3. Redeploy after adding api/ folder

### 401 on Static Files (manifest.json, etc.)

**Problem:** Vercel Authentication blocking requests

**Solutions:**
1. Use the production URL (not preview URL)
2. Disable auth: Dashboard → Settings → Deployment Protection → Off

### URL Has Random Characters

**Example:** `project-abc123-user.vercel.app` instead of `project.vercel.app`

**Cause:** Using `builds` in vercel.json triggers legacy mode

**Solution:** Switch to minimal `rewrites` config

### Environment Variables Not Working

1. **Redeploy** after adding/changing variables
2. Check exact name match (case-sensitive)
3. Check you're not using `REACT_APP_` prefix for server-side vars
4. View logs: Dashboard → Functions → Select function → Logs

### Build Fails

Check:
1. `npm run build` works locally
2. All dependencies in `package.json` (not just devDependencies)
3. No hardcoded paths that only exist locally

---

## Testing Serverless Functions Locally

### Option 1: Vercel Dev

```bash
vercel dev
# Runs at http://localhost:3000 with full serverless support
```

### Option 2: Manual Test Script

```javascript
// test-api.js
const handler = require('./api/chat.js').default;

const req = {
  method: 'POST',
  body: {
    messages: [{ role: 'user', content: 'Hello' }],
    model: 'gpt-4o-mini',
    userApiKey: process.env.OPENAI_API_KEY
  }
};

const res = {
  setHeader: () => {},
  status: (code) => ({
    json: (data) => console.log(code, data),
    end: () => {}
  })
};

handler(req, res);
```

Run with:
```bash
OPENAI_API_KEY=sk-... node test-api.js
```

---

## Deployment Checklist

- [ ] `api/chat.js` exists in project root
- [ ] `vercel.json` has correct rewrites
- [ ] Environment variables set in Vercel dashboard
- [ ] `vercel-build` script in package.json (if using static-build)
- [ ] `npm run build` works locally
- [ ] Redeployed after env variable changes
