# ChatGPT Response Format for Chat Viewer

How to parse OpenAI API responses and display them in a chat interface.

---

## API Response Structures

### Chat Completions API (Standard)

**Endpoint:** `POST https://api.openai.com/v1/chat/completions`

**Response:**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1699000000,
  "model": "gpt-4o-mini",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 15,
    "total_tokens": 25
  }
}
```

**Extract content:**
```javascript
const content = data.choices[0].message.content;
```

---

### Responses API (Web Search)

**Endpoint:** `POST https://api.openai.com/v1/responses`

**Response:**
```json
{
  "id": "resp_abc123",
  "object": "response",
  "created_at": 1699000000,
  "status": "completed",
  "output_text": "Based on my web search, the weather in SF is 65°F...",
  "output": [
    {
      "type": "web_search_call",
      "id": "ws_123",
      "status": "completed"
    },
    {
      "type": "message",
      "id": "msg_123",
      "status": "completed",
      "role": "assistant",
      "content": [
        {
          "type": "output_text",
          "text": "Based on my web search..."
        }
      ]
    }
  ],
  "usage": {
    "input_tokens": 20,
    "output_tokens": 150
  }
}
```

**Extract content:**
```javascript
// Primary method - use output_text directly
const content = data.output_text;

// Fallback - dig into output array
if (!content && data.output) {
  for (const item of data.output) {
    if (item.type === 'message' && item.content) {
      for (const c of item.content) {
        if (c.type === 'output_text') {
          content = c.text;
          break;
        }
      }
    }
  }
}
```

---

## Backend Parsing (api/chat.js)

```javascript
export default async function handler(req, res) {
  const { messages, model, webSearch } = req.body;

  try {
    let assistantContent;

    if (webSearch) {
      // Responses API
      const response = await fetch('https://api.openai.com/v1/responses', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
        },
        body: JSON.stringify({
          model: model || 'gpt-4o-mini',
          tools: [{ type: 'web_search' }],
          tool_choice: 'auto',
          input: messages[messages.length - 1].content,
        }),
      });

      const data = await response.json();

      // Extract from Responses API format
      assistantContent = data.output_text;

      // Fallback extraction
      if (!assistantContent && data.output) {
        for (const item of data.output) {
          if (item.type === 'message' && item.content) {
            for (const c of item.content) {
              if (c.type === 'output_text' && c.text) {
                assistantContent = c.text;
                break;
              }
            }
          }
          if (assistantContent) break;
        }
      }

    } else {
      // Chat Completions API
      const response = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
        },
        body: JSON.stringify({
          model: model || 'gpt-4o-mini',
          max_tokens: 4096,
          messages: messages,
        }),
      });

      const data = await response.json();

      // Extract from Chat Completions format
      assistantContent = data.choices[0].message.content;
    }

    // Return unified format to frontend
    return res.status(200).json({ content: assistantContent });

  } catch (error) {
    return res.status(500).json({ error: error.message });
  }
}
```

---

## Frontend Chat Viewer Integration

### State Structure

```javascript
const [messages, setMessages] = useState([]);
// Each message: { role: 'user' | 'assistant', content: string }
```

### Sending and Receiving

```javascript
const sendMessage = async () => {
  const userMessage = { role: 'user', content: userInput };
  const newMessages = [...messages, userMessage];
  setMessages(newMessages);
  setIsLoading(true);

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: newMessages.map(m => ({ role: m.role, content: m.content })),
        model: selectedModel,
        webSearch: webSearchEnabled,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Request failed');
    }

    // Backend returns unified { content: "..." } format
    const assistantMessage = {
      role: 'assistant',
      content: data.content,
    };

    setMessages([...newMessages, assistantMessage]);

  } catch (error) {
    console.error('Error:', error);
    // Optionally add error message to chat
    setMessages([...newMessages, {
      role: 'assistant',
      content: `Error: ${error.message}`,
    }]);
  } finally {
    setIsLoading(false);
  }
};
```

### Rendering Messages

```jsx
<div className="chat-container">
  {messages.map((msg, index) => (
    <div
      key={index}
      className={`message ${msg.role === 'user' ? 'user-message' : 'assistant-message'}`}
    >
      <div className="message-role">
        {msg.role === 'user' ? 'You' : 'ChatGPT'}
      </div>
      <div className="message-content">
        {msg.content}
      </div>
    </div>
  ))}

  {isLoading && (
    <div className="message assistant-message">
      <div className="message-role">ChatGPT</div>
      <div className="message-content">Thinking...</div>
    </div>
  )}
</div>
```

---

## Error Handling

### API Error Response

```json
{
  "error": {
    "message": "Incorrect API key provided",
    "type": "invalid_request_error",
    "code": "invalid_api_key"
  }
}
```

### Handling in Backend

```javascript
if (!response.ok) {
  const responseText = await response.text();
  let errorMessage = 'API request failed';

  try {
    const errorData = JSON.parse(responseText);
    errorMessage = errorData.error?.message || errorMessage;
  } catch (e) {
    errorMessage = responseText || errorMessage;
  }

  throw new Error(errorMessage);
}
```

### Common Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 401 | Invalid API key | Check key format and validity |
| 429 | Rate limited | Wait and retry, or upgrade plan |
| 500 | OpenAI server error | Retry after a moment |
| 503 | Service overloaded | Retry with backoff |

---

## Quick Reference

| API | Endpoint | Extract Content |
|-----|----------|-----------------|
| Chat Completions | `/v1/chat/completions` | `data.choices[0].message.content` |
| Responses (Web Search) | `/v1/responses` | `data.output_text` |

### Unified Backend Response

Always return the same format from your backend:

```javascript
// Success
res.status(200).json({ content: assistantContent });

// Error
res.status(500).json({ error: errorMessage });
```

This way your frontend only needs to handle one format regardless of which OpenAI API was used.
