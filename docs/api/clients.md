# Clients Module

> [!WARNING]
> **Experimental.** This module is a prototype and needs a major refactor.
> The current serialization (pickle + base64 + msgpack), error handling, and
> reconnection logic are not production-grade. Use for experimentation only.

The `REvoDesign.clients` package provides WebSocket-based networking for
real-time collaboration between REvoDesign instances. Two peer instances can
connect via WebSockets to share views, mutant trees, configurations, and
PyMOL sessions.

## Architecture

```
┌─────────────────┐           WebSocket           ┌─────────────────┐
│  Instance A     │◄─────────────────────────────►│  Instance B     │
│  (Server mode)  │     ws://host:port             │  (Client mode)  │
│                 │                                │                 │
│  REvoDesign-    │     msgpack + pickle +         │  REvoDesign-    │
│  WebSocketServer│     base64 serialization       │  WebSocketClient│
└─────────────────┘                                └─────────────────┘
```

One instance starts a WebSocket server (`REvoDesignWebSocketServer`), and
other instances connect as clients (`REvoDesignWebSocketClient`). The server
supports optional key-based authentication, view broadcasting, and mutant
tree synchronisation.

### Supported data types

Data exchanged between peers is serialized via pickle, encoded in base64,
and packed with msgpack. The `Broadcaster` class enforces a whitelist of
allowed data types:

- `MutantTree` -- mutant tree for synchronised mutagenesis
- `PyMOL_prompt` -- PyMOL command to execute on peers
- `PyMOL_selection` -- atom selections
- `ViewUpdate` -- camera view matrix
- `ConfigItem` -- configuration item changes
- `ClientInfo` -- peer metadata (user, node, OS)
- `Text` -- plain text chat
- `UUID` -- client identity
- `UserTree` -- peer list for the UI tree widget
- `PyMOL_session` -- serialised PyMOL session
- `MessageStack` -- batched messages

## Module Reference

The module is located at `src/REvoDesign/clients/QtSocketConnector.py` (namespace package, no `__init__.py`). Key classes:

- **`Client`** — Represents a connected peer with identity, socket, and metadata.
- **`MeetingRoom`** — Manages connected clients, tracks attendance, and handles message routing.
- **`Broadcaster`** — Sends data to all connected clients with type whitelisting and serialization.
- **`REvoDesignWebSocketServer`** — Qt-based WebSocket server listening on a configurable port with optional key authentication.
- **`REvoDesignWebSocketClient`** — Qt-based WebSocket client that connects to a remote server instance.
