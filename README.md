# NC DMV Permit-Test Appointment Monitor

A containerized monitoring service that automatically checks for available North Carolina DMV appointments and sends notifications via Home Assistant when openings are found.

## Features

- 🔄 **Continuous Monitoring** - Automatically checks for appointment availability at configurable intervals
- 📍 **Location-Based** - Monitors the closest DMV locations to your coordinates
- 🎯 **Category Targeting** - Supports multiple appointment types (Knowledge Test, Permits, etc.)
- 🏠 **Home Assistant Integration** - Webhook notifications for custom automations
- 🐳 **Fully Dockerized** - Easy deployment with Docker Compose
- 📊 **Structured Logging** - Configurable log levels (DEBUG, INFO, WARNING, ERROR)
- ⚡ **Fast & Efficient** - Built with uv for lightning-fast dependency management
- 🔒 **Headless Browser** - Uses Browserless Chrome for reliable automation

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  DMV Monitor    │────▶│  Browserless     │────▶│  NC DMV Website │
│  (Python + uv)  │     │  (Chrome)        │     │                 │
└────────┬────────┘     └──────────────────┘     └─────────────────┘
         │
         │ Webhook
         ▼
┌─────────────────┐
│ Home Assistant  │
│  Automation     │
└─────────────────┘
```

## Prerequisites

- Docker and Docker Compose
- Home Assistant instance (for notifications)
- Basic knowledge of Docker environment variables

## Quick Start

### 1. Clone the Repository

```
git clone <your-repo-url>
cd nc-dmv-monitor
```

### 2. Configure Environment Variables

Edit `docker-compose.yml` and update the environment variables:

```
environment:
  # Your location coordinates
  LATITUDE: 35.5843        # Fuquay-Varina, NC
  LONGITUDE: -78.8
  
  # How often to check (in seconds)
  CHECK_INTERVAL: 60       # Check every minute
  
  # Number of closest locations to monitor
  MAX_LOCATIONS: 25
  
  # Home Assistant configuration
  HOME_ASSISTANT_URL: http://homeassistant.local:8123
  HA_WEBHOOK_ID: dmv_appointment_found
  
  # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  LOG_LEVEL: INFO
```

### 3. Set Up Home Assistant Automation

In Home Assistant, create a new automation:

**Settings → Automations → Create Automation → Edit in YAML**

```
alias: DMV Appointment Notification
description: Sends notification when DMV appointments are found
trigger:
  - platform: webhook
    webhook_id: dmv_appointment_found
    allowed_methods:
      - POST
    local_only: false
condition: []
action:
  - service: notify.mobile_app_your_phone
    data:
      title: 🎉 DMV Appointments Available!
      message: >-
        {{ trigger.json.category }}: {{ trigger.json.location_count }} location(s)
        
        Closest: {{ trigger.json.closest_location }}
      data:
        tag: dmv_appointment
        priority: high
        ttl: 0
        clickAction: "{{ trigger.json.booking_url }}"
        actions:
          - action: URI
            title: Book Now
            uri: "{{ trigger.json.booking_url }}"
mode: single
```

### 4. Deploy

```
# Build and start services
docker-compose up --build -d

# View logs
docker-compose logs -f dmv-monitor
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BROWSERLESS_HOST` | `browserless` | Browserless service hostname |
| `BROWSERLESS_PORT` | `3000` | Browserless service port |
| `BROWSERLESS_TOKEN` | `""` | Optional auth token for Browserless |
| `LATITUDE` | `35.5843` | Your location latitude |
| `LONGITUDE` | `-78.8` | Your location longitude |
| `CHECK_INTERVAL` | `60` | Seconds between checks |
| `MAX_LOCATIONS` | `25` | Number of closest locations to monitor |
| `HOME_ASSISTANT_URL` | `http://homeassistant.local:8123` | Your Home Assistant URL |
| `HA_WEBHOOK_ID` | `dmv_appointment_found` | Webhook ID in Home Assistant |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### Finding Your Coordinates

1. Go to [Google Maps](https://maps.google.com)
2. Right-click your location
3. Click the coordinates to copy them
4. Format: `LATITUDE, LONGITUDE`

Example: Fuquay-Varina, NC = `35.5843, -78.8`

## Monitored Appointment Categories

Currently monitors:
- **Knowledge Test** - Written test, traffic signs, vision
- **Permits** - Adult permit, CDL

Additional categories can be added by updating the `CATEGORIES` dictionary in `main.py`.

## Webhook Payload

When availability is found, the following JSON payload is sent to Home Assistant:

```
{
  "category": "Knowledge Test",
  "location_count": 3,
  "closest_location": "Fuquay-Varina",
  "booking_url": "https://skiptheline.ncdot.gov/",
  "timestamp": "2025-10-05T23:00:00",
  "locations": [
    {
      "name": "Fuquay-Varina",
      "address": "Old Municipal Building, 131 S. Fuquay Ave., Fuquay-Varina, NC 27526",
      "rank": 1
    },
    {
      "name": "Garner",
      "address": "Forest Hills Shopping Center, 222 Forest Hills Drive, Garner, NC 27529",
      "rank": 2
    }
  ]
}
```

### Project Structure

```
nc-dmv-monitor/
├── main.py                 # Main application
├── pyproject.toml          # uv project configuration
├── uv.lock                 # Locked dependencies
├── Dockerfile              # Multi-stage Docker build
├── .dockerignore          # Docker build exclusions
└── README.md              # This file
```

## Troubleshooting

### Monitor not finding locations

**Issue:** "Found 0 locations"

**Solution:**
1. Check Browserless is running: `docker-compose ps`
2. Increase wait times in code if page loads slowly
3. Check logs with `LOG_LEVEL=DEBUG`

### Webhook not triggering

**Issue:** Home Assistant not receiving notifications

**Solution:**
1. Verify `HOME_ASSISTANT_URL` is correct
2. Check webhook ID matches in Home Assistant automation
3. Ensure Home Assistant is accessible from Docker network
4. Test webhook manually:
   ```
   curl -X POST http://homeassistant.local:8123/api/webhook/dmv_appointment_found \
     -H "Content-Type: application/json" \
     -d '{"test": "data"}'
   ```

### Browser crashes or timeouts

**Issue:** "Execution context was destroyed"

**Solution:**
1. Increase `CHECK_INTERVAL` to avoid rate limiting
2. Restart Browserless: `docker-compose restart browserless`
3. Increase Browserless memory in docker-compose.yml

### High CPU/Memory usage

**Solution:**
1. Reduce `MAX_LOCATIONS` (fewer locations to check)
2. Increase `CHECK_INTERVAL` (check less frequently)
3. Limit Browserless concurrent sessions in docker-compose.yml

## Acknowledgments

- Built with [uv](https://github.com/astral-sh/uv) - Ultra-fast Python package manager
- [Playwright](https://playwright.dev/) - Browser automation
- [Browserless](https://www.browserless.io/) - Headless Chrome management
- [Home Assistant](https://www.home-assistant.io/) - Home automation platform

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

---

**Note:** This tool is for personal use only. Please respect NC DMV's terms of service and avoid excessive request rates.
```