# Toggle Between Anthropic and ChatGPT

How to implement a provider toggle in a React app to switch between Claude (Anthropic) and ChatGPT (OpenAI).

---

## 1. State Setup

```javascript
// In ReportChat.js
const [aiProvider, setAiProvider] = useState('Anthropic'); // 'Anthropic' or 'ChatGPT'
const [apiKey, setApiKey] = useState('');
const [selectedModel, setSelectedModel] = useState('claude-3-5-haiku-20241022');
```

---

## 2. Define Models for Each Provider

```javascript
const anthropicModels = {
  'Claude 3.5 Haiku': 'claude-3-5-haiku-20241022',
  'Claude 3.5 Sonnet': 'claude-3-5-sonnet-20241022',
  'Claude Sonnet 4': 'claude-sonnet-4-20250514',
  'Claude Opus 4.5': 'claude-opus-4-5-20251101',
};

const openaiModels = {
  'GPT-4o Mini': 'gpt-4o-mini',
  'GPT-4o': 'gpt-4o',
  'GPT-4 Turbo': 'gpt-4-turbo',
  'GPT-3.5 Turbo': 'gpt-3.5-turbo',
  'o1': 'o1',
  'o1 Mini': 'o1-mini',
};

// Get current models based on provider
const models = aiProvider === 'ChatGPT' ? openaiModels : anthropicModels;
```

---

## 3. Reset Model When Provider Changes

```javascript
useEffect(() => {
  if (aiProvider === 'ChatGPT') {
    setSelectedModel('gpt-4o-mini'); // Default for ChatGPT
  } else {
    setSelectedModel('claude-3-5-haiku-20241022'); // Default for Anthropic
  }
}, [aiProvider]);
```

---

## 4. Toggle UI Component

```jsx
{/* AI Provider Toggle */}
<div style={styles.section}>
  <label style={styles.label}>AI Provider:</label>
  <div style={styles.providerToggle}>
    <button
      onClick={() => setAiProvider('ChatGPT')}
      style={{
        ...styles.providerBtn,
        ...(aiProvider === 'ChatGPT' ? styles.providerBtnActive : {}),
      }}
    >
      ChatGPT
    </button>
    <button
      onClick={() => setAiProvider('Anthropic')}
      style={{
        ...styles.providerBtn,
        ...(aiProvider === 'Anthropic' ? styles.providerBtnActive : {}),
      }}
    >
      Claude
    </button>
  </div>
</div>

{/* Dynamic API Key Label */}
<div style={styles.section}>
  <label style={styles.label}>
    {aiProvider === 'ChatGPT' ? 'OpenAI' : 'Anthropic'} API Key:
  </label>
  <input
    type="password"
    value={apiKey}
    onChange={(e) => setApiKey(e.target.value)}
    placeholder={aiProvider === 'ChatGPT' ? 'sk-...' : 'sk-ant-...'}
    style={styles.input}
  />
</div>

{/* Model Dropdown (uses dynamic models object) */}
<div style={styles.section}>
  <label style={styles.label}>
    {aiProvider === 'ChatGPT' ? 'OpenAI' : 'Claude'} Model:
  </label>
  <select
    value={selectedModel}
    onChange={(e) => setSelectedModel(e.target.value)}
    style={styles.select}
  >
    {Object.entries(models).map(([name, value]) => (
      <option key={value} value={value}>{name}</option>
    ))}
  </select>
</div>
```

---

## 5. Toggle Button Styles

```javascript
const styles = {
  providerToggle: {
    display: 'flex',
    gap: '0',
    borderRadius: '6px',
    overflow: 'hidden',
  },
  providerBtn: {
    flex: 1,
    padding: '10px 12px',
    border: 'none',
    fontSize: '14px',
    fontWeight: '500',
    background: '#2d2d44',
    color: '#888',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  providerBtnActive: {
    background: '#4da6ff',
    color: '#fff',
  },
};
```

---

## 6. Dynamic Labels in Chat

Update any hardcoded "Claude" references:

```jsx
{/* Info banner */}
<div style={styles.infoBanner}>
  {reportCount} report(s) sent to {aiProvider === 'ChatGPT' ? 'ChatGPT' : 'Claude'}
</div>

{/* Message role label */}
<div style={styles.messageRole}>
  {msg.role === 'user' ? 'You' : (aiProvider === 'ChatGPT' ? 'ChatGPT' : 'Claude')}
</div>

{/* Loading indicator */}
{isLoading && (
  <div style={styles.messageRole}>
    {aiProvider === 'ChatGPT' ? 'ChatGPT' : 'Claude'}
  </div>
  <div style={styles.messageContent}>Thinking...</div>
)}
```

---

## 7. API Call Logic (see 02-web-search-frontend-backend.md for full details)

The `sendMessage` function needs to handle both providers:

```javascript
if (aiProvider === 'ChatGPT') {
  // Call OpenAI API or your /api/chat backend
} else {
  // Call Anthropic API directly (with dangerous-direct-browser-access header)
}
```

---

## Key Points

1. **State**: Track `aiProvider`, reset `selectedModel` when provider changes
2. **Models**: Maintain separate model objects for each provider
3. **UI**: Dynamic labels, placeholders, and toggle buttons
4. **API**: Different endpoints and request formats for each provider
