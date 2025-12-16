# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TWS Monitoring is an Interactive Brokers TWS API health monitoring service. It continuously checks TWS API availability using the `ib_insync` library and sends Telegram alerts on status changes.

## Commands

```bash
./compose.sh    # Remove old containers, rebuild, and start services
./logs.sh       # Tail Docker logs for all monitoring containers
./update.sh     # Git pull + compose.sh + logs.sh
```

## Architecture

- **Single async Python service** (`server/server.py`) handles all monitoring logic
- **Multiple Docker containers** run independently for different TWS instances (configured in `docker-compose.yml`)
- **Network mode**: Containers use `network_mode: "container:openvpn"` to share the OpenVPN container's network
- **Monitoring loop**: Connects to TWS API every 60 seconds, requests server time to verify responsiveness
- **Notifications**: Sends Telegram messages on state transitions (up→down, down→up) and hourly reminders when down

## Key Files

| File | Purpose |
|------|---------|
| `server/server.py` | Main monitoring service with async health check loop |
| `docker-compose.yml` | Service definitions with TWS host/port per instance |
| `.env` | User secrets: `BOT_TOKEN`, `CHAT_ID` (not in repo) |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | Yes | Telegram bot token |
| `CHAT_ID` | Yes | Telegram chat ID for alerts |
| `TWS_HOST` | No | TWS API host (default: localhost) |
| `TWS_PORT` | No | TWS API port (default: 9999) |
| `TWS_CLIENT_ID` | No | TWS client ID (default: 10) |
| `CONTAINER_NAME` | No | Identifier in Telegram messages |
| `HOURLY_REMINDER` | No | Reminder interval in seconds (default: 3600) |

## Dependencies

Python 3.11 with: `ib-insync`, `ibapi`, `requests`
