# Frontend Architecture

## Overview

The BotGPT frontend is built with a modular, scalable architecture following React best practices. The codebase is organized into clear layers with separation of concerns.

## Directory Structure

```
src/
├── components/          # Reusable UI components
│   └── ui/             # Base UI components (Button, Input, Card, LoadingSpinner, Toast)
├── features/           # Feature modules (self-contained feature logic)
│   ├── auth/          # Authentication pages and logic
│   ├── dashboard/     # Dashboard with sidebar
│   ├── conversation/   # Chat interface and message handling
│   ├── profile/       # User profile page
│   └── updates/       # Toast notifications system
├── services/          # External service integrations
│   ├── api/          # API client and endpoint definitions
│   │   ├── client.ts        # Axios instance with interceptors
│   │   ├── conversations.ts # Conversation API endpoints
│   │   └── documents.ts     # Document API endpoints
│   ├── auth/         # Authentication service
│   │   └── mockAuth.ts      # Mock auth (replaceable with real auth)
│   └── socket.ts     # Socket.IO client service
├── state/            # Recoil state management
│   └── atoms/        # State atoms
│       ├── auth.ts           # Authentication state
│       └── conversations.ts  # Conversation state
├── hooks/            # Custom React hooks
│   └── useConversationPreload.ts # Preload conversation data
├── types/            # TypeScript type definitions
│   └── index.ts      # Shared types and interfaces
├── utils/            # Utility functions
│   └── cn.ts         # Tailwind class name merger
└── config/           # Configuration constants
    └── index.ts       # API URLs and endpoints
```

## Architecture Principles

### 1. Modular Features
Each feature is self-contained with its own components, logic, and state management needs. Features can be easily added, removed, or modified without affecting others.

### 2. Reusable Components
UI components in `components/ui/` are designed to be reusable across the application. They follow a consistent API and styling approach.

### 3. Service Layer
All external API calls and integrations are abstracted into service modules. This makes it easy to:
- Mock services for testing
- Replace implementations (e.g., mock auth → real auth)
- Centralize error handling

### 4. State Management
Recoil is used for global state management. State is organized by domain (auth, conversations) and kept close to where it's used.

### 5. Type Safety
Full TypeScript coverage ensures type safety across the application. Shared types are defined in `types/` and reused throughout.

## Key Features

### Authentication
- **Location**: `features/auth/`
- **Service**: `services/auth/mockAuth.ts`
- **State**: `state/atoms/auth.ts`
- Mock authentication that can be easily replaced with real auth

### Dashboard
- **Location**: `features/dashboard/`
- **Components**: `DashboardPage`, `Sidebar`
- ChatGPT-like interface with sidebar for conversation management
- Real-time conversation list updates

### Conversation Window
- **Location**: `features/conversation/`
- **Component**: `ConversationWindow`
- Features:
  - Real-time messaging via Socket.IO
  - Multi-document PDF upload
  - Message history
  - Typing indicators
  - Document management

### Socket.IO Integration
- **Service**: `services/socket.ts`
- Handles real-time communication with backend
- Automatic reconnection
- Room-based messaging

### Updates/Notifications
- **Location**: `features/updates/`
- Toast notification system
- Context-based API for showing notifications
- Auto-dismiss with configurable duration

## Data Flow

1. **User Action** → Component
2. **Component** → Service/API call
3. **Service** → Backend API
4. **Response** → Update Recoil state
5. **State Change** → Re-render components
6. **Socket.IO** → Real-time updates → Update state

## State Management Flow

```
User Action
    ↓
Component calls service
    ↓
Service makes API call
    ↓
Update Recoil atom
    ↓
Components re-render with new state
```

## Adding New Features

1. Create feature directory in `features/`
2. Add components specific to the feature
3. Create API endpoints in `services/api/` if needed
4. Add Recoil atoms in `state/atoms/` if global state is needed
5. Add routes in `App.tsx`
6. Use reusable UI components from `components/ui/`

## Best Practices

1. **Component Composition**: Build complex components from simple, reusable ones
2. **Separation of Concerns**: Keep UI, logic, and data separate
3. **Type Safety**: Use TypeScript types throughout
4. **Error Handling**: Handle errors gracefully with user feedback
5. **Loading States**: Show loading indicators for async operations
6. **Accessibility**: Use semantic HTML and ARIA labels
7. **Performance**: Use React.memo, useMemo, useCallback where appropriate

## Environment Configuration

Configuration is managed through environment variables:
- `VITE_API_BASE_URL`: Backend API URL
- `VITE_SOCKET_URL`: Socket.IO server URL

## Testing Strategy

The architecture supports easy testing:
- Services can be mocked
- Components can be tested in isolation
- State can be tested independently
- API calls can be intercepted

## Future Enhancements

- Add React Query for better data fetching and caching
- Implement proper error boundaries
- Add unit and integration tests
- Add Storybook for component documentation
- Implement real authentication (replace mock)
- Add dark/light theme toggle
- Add internationalization (i18n)

