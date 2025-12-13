# Web Search for ChatGPT: Frontend to Backend

How to implement web search using OpenAI's Responses API, with a secure backend to protect API keys.

---

## Architecture

```
Frontend (React)          Backend (Vercel Serverless)       OpenAI
     |                            |                           |
     |-- POST /api/chat --------->|                           |
     |   {webSearch: true}        |-- /v1/responses --------->|
     |                            |   {tools: [web_search]}   |
     |                            |<-- response --------------|
     |<-- {content: "..."}--------|                           |
```

---

## 1. Frontend: Web Search Checkbox

```javascript
// State
const [webSearchEnabled, setWebSearchEnabled] = useState(false);

// Only show for ChatGPT
{aiProvider === 'ChatGPT' && (
  <div style={styles.section}>
    <label style={styles.checkboxLabel}>
      <input
        type="checkbox"
        checked={webSearchEnabled}
        onChange={(e) => setWebSearchEnabled(e.target.checked)}
        style={styles.checkbox}
      />
      Enable Web Search
    </label>
  </div>
)}
```

---

## 2. Frontend: Send Request to Backend

```javascript
const sendMessage = async () => {
  // Build messages array
  const openaiMessages = [];
  if (systemPrompt) {
    openaiMessages.push({ role: 'system', content: systemPrompt });
  }
  openaiMessages.push(...messages.map(m => ({ role: m.role, content: m.content })));
  openaiMessages.push({ role: 'user', content: userInput });

  // Call YOUR backend (not OpenAI directly)
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: openaiMessages,
      model: selectedModel,
      webSearch: webSearchEnabled,  // <-- Pass web search flag
      userApiKey: apiKey,           // User's own key (optional)
      accessCode: accessCode,       // For shared key (optional)
    }),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.error || 'API request failed');
  }

  const data = await response.json();
  // data.content contains the assistant's response
};
```

---

## 3. Backend: api/chat.js (Vercel Serverless)

```javascript
// api/chat.js
export default async function handler(req, res) {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { messages, model, webSearch, userApiKey, accessCode } = req.body;

  // Determine API key
  let apiKey;
  if (userApiKey) {
    apiKey = userApiKey;
  } else if (accessCode === process.env.ACCESS_CODE) {
    apiKey = process.env.OPENAI_API_KEY;
  } else {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  try {
    let assistantContent;

    if (webSearch) {
      // === WEB SEARCH: Use Responses API ===
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
          input: messages[messages.length - 1].content, // Last user message
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error?.message || 'Web search failed');
      }

      const data = await response.json();
      assistantContent = data.output_text; // Direct property

    } else {
      // === STANDARD: Use Chat Completions API ===
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
        const error = await response.json();
        throw new Error(error.error?.message || 'Chat request failed');
      }

      const data = await response.json();
      assistantContent = data.choices[0].message.content;
    }

    return res.status(200).json({ content: assistantContent });

  } catch (error) {
    console.error('API error:', error);
    return res.status(500).json({ error: error.message });
  }
}
```

---

## 4. OpenAI Responses API (Web Search)

### Request Format

```javascript
{
  model: 'gpt-4o-mini',
  tools: [{ type: 'web_search' }],
  tool_choice: 'auto',
  input: 'What is the weather in San Francisco today?'
}
```

### Response Format

```javascript
{
  "id": "resp_123",
  "output_text": "The weather in San Francisco today is...",  // <-- Use this
  "output": [
    {
      "type": "web_search_call",
      "id": "ws_123",
      "status": "completed"
    },
    {
      "type": "message",
      "content": [...]
    }
  ]
}
```

**Key:** Use `data.output_text` for the final response text.

---

## 5. Chat Completions API (Standard)

### Request Format

```javascript
{
  model: 'gpt-4o-mini',
  max_tokens: 4096,
  messages: [
    { role: 'system', content: 'You are a helpful assistant.' },
    { role: 'user', content: 'Hello!' }
  ]
}
```

### Response Format

```javascript
{
  "id": "chatcmpl-123",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"  // <-- Use this
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {...}
}
```

**Key:** Use `data.choices[0].message.content` for the response.

---

## Key Differences

| Feature | Chat Completions | Responses (Web Search) |
|---------|------------------|------------------------|
| Endpoint | `/v1/chat/completions` | `/v1/responses` |
| Input | `messages` array | `input` string |
| Output | `choices[0].message.content` | `output_text` |
| Web Search | Not available | `tools: [{type: 'web_search'}]` |

---

## Security Notes

1. **Never expose API keys in frontend** - always use a backend
2. **Use environment variables** for API keys in Vercel
3. **Access code pattern** - allows sharing without exposing key:
   - User enters access code in frontend
   - Backend validates code, uses stored API key
