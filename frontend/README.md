# BotGPT Frontend

A modern React frontend for the BotGPT conversational AI application, built with Vite, TypeScript, Tailwind CSS, and Recoil.

## 🚀 Features

- **Authentication**: Mock authentication system (ready for real auth integration)
- **Dashboard**: ChatGPT-like interface with sidebar for managing conversations
- **Conversations**: Real-time chat interface with Socket.IO integration
- **Document Upload**: Multi-document PDF upload support for RAG
- **Chat Preloading**: Efficient conversation preloading for better UX
- **Profile Management**: User profile and settings page
- **Modular Architecture**: Reusable components and services

## 🛠️ Tech Stack

- **Framework**: React 19 + TypeScript
- **Build Tool**: Vite
- **Package Manager**: Bun
- **Styling**: Tailwind CSS
- **State Management**: Recoil
- **Routing**: React Router v7
- **HTTP Client**: Axios
- **Real-time**: Socket.IO Client
- **Icons**: Lucide React

## 📦 Installation

```bash
# Install dependencies
bun install
```

## 🏃 Development

```bash
# Start development server
bun dev
```

The app will be available at `http://localhost:5173`

## 🏗️ Project Structure

```
src/
├── components/          # Reusable UI components
│   └── ui/             # Base UI components (Button, Input, Card, etc.)
├── features/           # Feature modules
│   ├── auth/          # Authentication
│   ├── dashboard/     # Dashboard and sidebar
│   ├── conversation/   # Chat interface
│   └── profile/       # User profile
├── services/          # API and external services
│   ├── api/          # API client and endpoints
│   ├── auth/         # Authentication service
│   └── socket.ts     # Socket.IO service
├── state/            # Recoil state management
│   └── atoms/        # State atoms
├── hooks/            # Custom React hooks
├── types/            # TypeScript type definitions
├── utils/            # Utility functions
└── config/           # Configuration constants
```

## 🔧 Configuration

Create a `.env` file based on `.env.example`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_SOCKET_URL=http://localhost:8000
```

## 📝 Key Features Implementation

### Authentication
- Mock authentication service (easily replaceable with real auth)
- Persistent session via localStorage
- Protected routes

### Dashboard
- Sidebar with conversation list
- Real-time conversation updates
- Create, select, and delete conversations

### Conversation Window
- Real-time message delivery via Socket.IO
- Multi-document upload support
- Message history with proper formatting
- Typing indicators

### State Management
- Recoil atoms for global state
- Optimistic updates
- Efficient re-renders

## 🚢 Building for Production

```bash
# Build for production
bun run build

# Preview production build
bun run preview
```

## 📄 License

MIT
