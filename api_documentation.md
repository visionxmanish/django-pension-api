# Pension API Documentation

This document provides details on the available API endpoints, including `curl` examples for testing.

## Base URL
Default local development URL: `http://127.0.0.1:8000`

---

## 1. Pensioner Registration & Verification

### Register Pensioner
Register a new pensioner with their face data.
- **URL**: `/register/`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`

**Request Parameters:**
- `pension_id` (string): Unique ID of the pensioner.
- `name` (string): Full name.
- `file` (file): Image file containing the pensioner's face.

**Curl Example:**
```bash
curl -X POST http://127.0.0.1:8000/register/ \
  -F "pension_id=P12345" \
  -F "name=John Doe" \
  -F "file=@/path/to/face_image.jpg"
```

### Verify Pensioner (Image)
Verify a pensioner's identity using a single image.
- **URL**: `/verify/`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`

**Curl Example:**
```bash
curl -X POST http://127.0.0.1:8000/verify/ \
  -F "pension_id=P12345" \
  -F "file=@/path/to/test_image.jpg"
```

### Verify Liveness (Video)
Perform liveness and face verification using a video.
- **URL**: `/verify-liveness-video/`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`

**Request Parameters:**
- `pension_id` (string): Pensioner ID.
- `verification_type` (string): Required actions (e.g., `smile`, `move_head_left`, `move_head_right`).
- `file` (file): MP4 video file.

**Curl Example:**
```bash
curl -X POST http://127.0.0.1:8000/verify-liveness-video/ \
  -F "pension_id=P12345" \
  -F "verification_type=smile,turn_left" \
  -F "file=@/path/to/video.mp4"
```

---

## 2. Nominee Management

### Register Nominee
Register a nominee for an existing pensioner.
- **URL**: `/nominee/register/`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`

**Request Parameters:**
- `pension_id` (string): The pensioner's ID.
- `nominee_pension_id` (string): Unique ID for the nominee.
- `name` (string): Nominee's name.
- `relation` (string): Relation to the pensioner.
- `file` (file): Nominee's face image.

**Curl Example:**
```bash
curl -X POST http://127.0.0.1:8000/nominee/register/ \
  -F "pension_id=P12345" \
  -F "nominee_pension_id=N67890" \
  -F "name=Jane Doe" \
  -F "relation=Spouse" \
  -F "file=@/path/to/nominee_face.jpg"
```

### Edit Nominee
- **URL**: `/nominee/edit/`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`

**Curl Example:**
```bash
curl -X POST http://127.0.0.1:8000/nominee/edit/ \
  -F "nominee_pension_id=N67890" \
  -F "relation=Spouse" \
  -F "file=@/path/to/new_nominee_face.jpg"
```

### Delete Nominee
- **URL**: `/nominee/delete/`
- **Method**: `POST`
- **Content-Type**: `application/json`

**Curl Example:**
```bash
curl -X POST http://127.0.0.1:8000/nominee/delete/ \
  -H "Content-Type: application/json" \
  -d '{"nominee_id": "N67890"}'
```

### Verify Nominee Liveness (Video)
Verify a nominee's identity. **Only works if the pensioner is marked as deceased.**
- **URL**: `/nominee/verify-liveness/`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`

**Curl Example:**
```bash
curl -X POST http://127.0.0.1:8000/nominee/verify-liveness/ \
  -F "nominee_pension_id=N67890" \
  -F "verification_type=smile" \
  -F "file=@/path/to/nominee_video.mp4"
```

### Get Nominees By Parent (Integration-friendly)
- **URL**: `/nominee/parent/{pension_id}/`
- **Method**: `GET`
- **Description**: Returns both parent details and child nominees in one response.

**Response shape:**
```json
{
  "parent": {
    "id": 1,
    "pension_id": "P12345",
    "name": "John Doe",
    "is_active": true,
    "is_deceased": false
  },
  "nominees": [
    {
      "id": 1,
      "nominee_pension_id": "N67890",
      "name": "Jane Doe",
      "relation": "Spouse",
      "is_active": true,
      "created_at": "2026-04-23T12:00:00Z",
      "updated_at": "2026-04-23T12:00:00Z"
    }
  ]
}
```

---

## 3. Administrative Endpoints

### Mark Pensioner as Deceased
Update a pensioner's status.
- **URL**: `/mark-deceased/`
- **Method**: `POST`
- **Content-Type**: `application/json`

**Request Body:**
```json
{
  "pension_id": "P12345",
  "is_deceased": true
}
```

**Curl Example:**
```bash
curl -X POST http://127.0.0.1:8000/mark-deceased/ \
  -H "Content-Type: application/json" \
  -d '{"pension_id": "P12345", "is_deceased": true}'
```

### Get Dashboard Stats
- **URL**: `/api-admin/dashboard/`
- **Method**: `GET`

**Curl Example:**
```bash
curl -X GET http://127.0.0.1:8000/api-admin/dashboard/
```

### List Users
- **URL**: `/api-admin/users/`
- **Method**: `GET` (paginated)
+
+**Query params:** `q`, `is_active=true|false`, `is_deceased=true|false`

**Curl Example:**
```bash
curl -X GET http://127.0.0.1:8000/api-admin/users/
```

### Create User (Admin)
- **URL**: `/api-admin/users/`
- **Method**: `POST`
- **Content-Type**: `application/json` or `multipart/form-data`

**Curl Example (no face file):**
```bash
curl -X POST http://127.0.0.1:8000/api-admin/users/ \
  -H "Content-Type: application/json" \
  -d '{"pension_id": "P999", "name": "New User", "is_active": true, "is_deceased": false}'
```

### Get / Update / Delete User (Admin)
- **URL**: `/api-admin/users/{pension_id}/`
- **Methods**: `GET`, `PATCH`, `PUT`, `DELETE`

**Curl Example (PATCH):**
```bash
curl -X PATCH http://127.0.0.1:8000/api-admin/users/P12345/ \
  -H "Content-Type: application/json" \
  -d '{"name": "John Updated", "is_active": false}'
```

### Admin Nominees
- **List/Create**: `GET/POST /api-admin/nominees/`
- **Detail/Update/Delete**: `GET/PATCH/PUT/DELETE /api-admin/nominees/{nominee_pension_id}/`
- **List nominees for user**: `GET /api-admin/users/{pension_id}/nominees/`
- **Parent+nominees object**: `GET /api-admin/parents/{pension_id}/nominees/`

### Verification History (Admin)
- **User verifications**: `GET /api-admin/verifications/`
- **Nominee verifications**: `GET /api-admin/nominee-verifications/`

### Ops / Meta
- **Health**: `GET /api-admin/health/`
- **Meta**: `GET /api-admin/meta/`
