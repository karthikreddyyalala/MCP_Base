# API Reference

## Authentication

All requests require a Bearer token in the Authorization header.

```
Authorization: Bearer <token>
```

Tokens expire after 24 hours. Refresh via `POST /auth/refresh`.

## Endpoints

### GET /health

Returns 200 if the service is healthy. No auth required.

### POST /documents

Upload a document for processing.

**Body:** `multipart/form-data` with field `file` (PDF or DOCX, max 50MB)

**Response:** `{"id": "doc_abc123", "status": "processing"}`
