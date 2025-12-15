# Chat App - AI Agent Instructions

## Architecture Overview
This is a real-time chat application with a microservices architecture using Docker Compose:
- **Backend**: FastAPI (Python) with Socket.IO for real-time messaging, SQLAlchemy 2.0+ for async database operations
- **Frontend**: Vue 3 with Vite, served via Nginx, using Socket.IO client for WebSocket connections
- **Database**: PostgreSQL with asyncpg driver

Key data flows:
- Users interact via `/widget` page (public chat interface)
- Admins manage via `/admin/*` routes (login required, token stored in localStorage)
- Real-time messages via Socket.IO rooms (session-based and operator rooms)
- File uploads served statically from `/uploads` directory

## Development Workflow
- **Start services**: `docker compose up -d --build` (builds and runs all containers)
- **Database operations**: Use `docker compose exec db sh -lc 'psql -U chatuser -d chatdb -c "..."'` for direct DB access
- **Backend API**: Runs on port 8000, includes REST endpoints under `/api` and WebSocket at `/ws/socket.io`
- **Frontend**: Runs on port 5173 (dev) or 80 (prod), built with Vite

## Code Patterns
- **Backend models**: SQLAlchemy declarative base in `backend/app/models.py`, enums for roles/status (e.g., `UserRole.ADMIN`)
- **API schemas**: Pydantic models in `backend/app/schemas.py` for request/response validation
- **Routes**: Modular routers in `backend/app/api/`, prefixed with `/api`, async dependencies for DB sessions
- **WebSocket events**: Handled in `backend/app/socket.py`, room-based messaging (e.g., `join_session` event)
- **Frontend components**: Page-based in `frontend/src/pages/`, router guards for admin auth
- **Authentication**: JWT tokens, password hashing with bcrypt, user roles (ADMIN/OPERATOR)

## Integration Points
- **CORS**: Enabled for all origins in FastAPI middleware
- **Static files**: Uploaded files mounted at `/uploads` in backend
- **Environment**: Backend uses `.env` file for config (DATABASE_URL, etc.)
- **Database migrations**: Not automated; schema changes require manual SQL or alembic setup

## Key Files
- `docker-compose.yml`: Service definitions and networking
- `backend/app/main.py`: FastAPI app setup with Socket.IO integration
- `backend/app/models.py`: Database models and relationships
- `frontend/src/router.js`: Vue routes with authentication guards
- `backend/requirements.txt`: Python dependencies (note: SQLAlchemy>=2.0 required)