# ChatGPT Vercel Deployment Guide

Complete guide for deploying a React app with ChatGPT (OpenAI) backend to Vercel.

---

## Two Deployment Options

| Option | Env Variables | Use Case |
|--------|---------------|----------|
| **A: User's Own Key** | Not required | Users enter their own OpenAI API key |
| **B: Shared Key** | Required | You provide API key, users enter access code |

**Why use `/api/chat` backend even without env variables?**

You still need the backend because:
1. **CORS** - OpenAI API blocks direct browser requests
2. **Web Search** - Responses API requires server-side calls
3. **Security** - Backend can validate requests, add rate limiting

---

## Option A: User Provides Their Own API Key

No environment variables needed. User enters their OpenAI key in the frontend.

### api/chat.js

```javascript
export default async function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const { messages, model, webSearch, userApiKey } = req.body;

  // User must provide their own key
  if (!userApiKey) {
    return res.status(400).json({ error: 'API key required' });
  }

  try {
    let content;

    if (webSearch) {
      // Web Search - Responses API
      const response = await fetch('https://api.openai.com/v1/responses', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${userApiKey}`,
        },
        body: JSON.stringify({
          model: model || 'gpt-4o-mini',
          tools: [{ type: 'web_search' }],
          tool_choice: 'auto',
          input: messages[messages.length - 1].content,
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error?.message || 'Web search failed');
      }

      const data = await response.json();
      content = data.output_text;

    } else {
      // Standard - Chat Completions API
      const response = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${userApiKey}`,
        },
        body: JSON.stringify({
          model: model || 'gpt-4o-mini',
          max_tokens: 4096,
          messages: messages,
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error?.message || 'Chat failed');
      }

      const data = await response.json();
      content = data.choices[0].message.content;
    }

    return res.status(200).json({ content });

  } catch (error) {
    console.error('OpenAI error:', error);
    return res.status(500).json({ error: error.message });
  }
}
```

### Frontend Call

```javascript
const response = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    messages: [{ role: 'user', content: 'Hello!' }],
    model: 'gpt-4o-mini',
    webSearch: false,
    userApiKey: apiKey,  // User's key from input field
  }),
});
```

---

## Option B: Shared Key with Access Code

You store the API key in Vercel. Users enter an access code to use it.

### api/chat.js

```javascript
export default async function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const { messages, model, webSearch, userApiKey, accessCode } = req.body;

  // Determine API key source
  let apiKey;

  if (userApiKey) {
    // User provided their own key
    apiKey = userApiKey;
  } else if (accessCode) {
    // User wants to use shared key - validate access code
    if (accessCode !== process.env.ACCESS_CODE) {
      return res.status(401).json({ error: 'Invalid access code' });
    }
    apiKey = process.env.OPENAI_API_KEY;
  } else {
    return res.status(400).json({ error: 'API key or access code required' });
  }

  if (!apiKey) {
    return res.status(500).json({ error: 'API key not configured' });
  }

  try {
    let content;

    if (webSearch) {
      const response = await fetch('https://api.openai.com/v1/responses', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          model: model || 'gpt-4o-mini',
          tools: [{ type: 'web_search' }],
          tool_choice: 'auto',
          input: messages[messages.length - 1].content,
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error?.message || 'Web search failed');
      }

      const data = await response.json();
      content = data.output_text;

    } else {
      const response = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          model: model || 'gpt-4o-mini',
          max_tokens: 4096,
          messages: messages,
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error?.message || 'Chat failed');
      }

      const data = await response.json();
      content = data.choices[0].message.content;
    }

    return res.status(200).json({ content });

  } catch (error) {
    console.error('OpenAI error:', error);
    return res.status(500).json({ error: error.message });
  }
}
```

### Environment Variables (Vercel Dashboard)

1. Go to **vercel.com** → Your Project → **Settings** → **Environment Variables**
2. Add:

| Key | Value |
|-----|-------|
| `OPENAI_API_KEY` | `sk-proj-...` |
| `ACCESS_CODE` | `mysecretcode` |

3. **Save** and **Redeploy**

### Frontend Call

```javascript
// Using access code (shared key)
const response = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    messages: [{ role: 'user', content: 'Hello!' }],
    model: 'gpt-4o-mini',
    webSearch: false,
    accessCode: 'mysecretcode',
  }),
});

// OR using own key
const response = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    messages: [{ role: 'user', content: 'Hello!' }],
    model: 'gpt-4o-mini',
    webSearch: false,
    userApiKey: 'sk-...',
  }),
});
```

---

## Required Files

### vercel.json

```json
{
  "rewrites": [
    { "source": "/api/:path*", "destination": "/api/:path*" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

### package.json (scripts)

```json
{
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "vercel-build": "react-scripts build"
  }
}
```

### File Structure

```
your-project/
├── api/
│   └── chat.js          # Serverless function (must be in root!)
├── src/
│   └── App.js
├── public/
├── package.json
└── vercel.json
```

---

## Deployment

```bash
cd your-project
vercel --prod
```

---

## Why /api/chat is Required

Even if users provide their own API key, you need the backend:

| Problem | Why Backend Solves It |
|---------|----------------------|
| **CORS blocked** | OpenAI rejects browser requests. Backend makes server-to-server call. |
| **Web search** | Responses API only works server-side |
| **Key validation** | Backend can check key format before calling OpenAI |
| **Error handling** | Unified error format for frontend |
| **Rate limiting** | Can add throttling to prevent abuse |

### What happens without backend:

```javascript
// This FAILS in browser - CORS error
await fetch('https://api.openai.com/v1/chat/completions', {
  headers: { 'Authorization': `Bearer ${userKey}` },
  // ...
});
// Error: blocked by CORS policy
```

### With backend:

```
Browser → /api/chat (your Vercel function) → api.openai.com
         (no CORS issue - server to server)
```

---

## Troubleshooting

### 404 on /api/chat

- `api/chat.js` must be in project root, not `src/api/`
- Check vercel.json has API rewrite before catch-all
- Redeploy after adding api folder

### CORS error

Add these headers to api/chat.js:
```javascript
res.setHeader('Access-Control-Allow-Origin', '*');
res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
if (req.method === 'OPTIONS') return res.status(200).end();
```

### 401 Invalid access code

- Check ACCESS_CODE env variable in Vercel matches frontend value
- Redeploy after changing env variables

### 500 API key not configured

- Set OPENAI_API_KEY in Vercel dashboard
- Make sure it starts with `sk-` (not `sk-ant-`)
- Redeploy

---

## Checklist

**Option A (User's key only):**
- [ ] `api/chat.js` in project root
- [ ] `vercel.json` with rewrites
- [ ] `vercel --prod`

**Option B (Shared key):**
- [ ] All of Option A, plus:
- [ ] `OPENAI_API_KEY` in Vercel env
- [ ] `ACCESS_CODE` in Vercel env
- [ ] Redeploy after setting env vars
