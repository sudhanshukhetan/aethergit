# AetherGit

No AI APIs. A zero-dependency local Node API runs the rule engine in `engine.js`.

## Run
```
npm start        # http://127.0.0.1:3000
npm test
```

## Files
- `server.js` local API + static host (binds to 127.0.0.1 only)
- `engine.js` extraction, quote verification, firewall, relinker, identity graph
- `index.html` UI (calls `/api/*`)
- `data/decisions.json` created on first save
- `tests/engine.test.js`

## API
| Route | Body | Returns |
|---|---|---|
| GET `/api/health` | | `{ok}` |
| POST `/api/extract` | `{text}` | `{result, anchor}` |
| GET/POST `/api/decisions`, DELETE `/api/decisions/:id` | decision | saved decisions |
| POST `/api/check` | `{title,file,line}` | `{status,hits}` |
| POST `/api/relink` | `{original,newFile}` | best match + score |
| POST `/api/identities` | `{text}` | merged clusters |
