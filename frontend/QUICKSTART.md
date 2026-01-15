# Quick Start Guide

## Prerequisites

- Bun installed (https://bun.sh)
- Backend running on `http://localhost:8000`

## Setup

1. **Install dependencies:**
   ```bash
   cd frontend
   bun install
   ```

2. **Configure environment:**
   The `.env` file is already created with default values. If your backend runs on a different port, update:
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   VITE_SOCKET_URL=http://localhost:8000
   ```

3. **Start development server:**
   ```bash
   bun dev
   ```

4. **Open in browser:**
   Navigate to `http://localhost:5173`

## First Steps

1. **Login:**
   - Use any email/password (demo mode)
   - Default: `demo@botconsulting.io` / any password

2. **Create a conversation:**
   - Click "New Chat" in the sidebar
   - Start typing messages

3. **Upload documents:**
   - Click the upload button in the conversation window
   - Select PDF files
   - Documents will be processed in the background

4. **View profile:**
   - Click "Profile" in the top bar
   - View your account information

## Features to Try

- ✅ Create multiple conversations
- ✅ Switch between conversations
- ✅ Send messages and receive AI responses
- ✅ Upload PDF documents for RAG
- ✅ Real-time message updates via Socket.IO
- ✅ Delete conversations
- ✅ View profile information

## Troubleshooting

### Backend Connection Issues
- Ensure backend is running on port 8000
- Check CORS settings in backend
- Verify API endpoints in browser network tab

### Socket.IO Connection Issues
- Check Socket.IO server is running
- Verify `VITE_SOCKET_URL` matches backend Socket.IO endpoint
- Check browser console for connection errors

### Build Issues
- Clear node_modules and reinstall: `rm -rf node_modules && bun install`
- Check Node.js/Bun version compatibility

## Development Tips

- Hot reload is enabled - changes reflect immediately
- Check browser console for errors
- Use React DevTools for component inspection
- Use Recoil DevTools for state inspection (if installed)

## Next Steps

- Replace mock auth with real authentication
- Add more features based on backend capabilities
- Customize styling and theme
- Add unit tests
- Set up CI/CD

