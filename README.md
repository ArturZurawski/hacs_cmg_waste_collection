# Waste Collection Integration - Technical Documentation

Home Assistant integration for waste collection schedules using EcoHarmonogram.pl API.

## Architecture

### Components

```
waste_collection/
├── __init__.py          # Integration setup, coordinator, daily update scheduler
├── api.py               # API client for EcoHarmonogram.pl
├── config_flow.py       # Multi-step configuration flow
├── sensor.py            # Sensor entities (individual, aggregate, info)
├── button.py            # Manual refresh button
├── const.py             # Constants and configuration keys
├── manifest.json        # Integration metadata
├── strings.json         # English translations
└── translations/
    └── pl.json          # Polish translations
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Daily Update (00:01) OR Manual Refresh Button Press        │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ DataUpdateCoordinator.async_request_refresh()              │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ WasteCollectionAPI.update()                                 │
│   • POST /v1/schedules                                      │
│   • Parse response                                          │
│   • Filter by selected waste types                          │
│   • Return (schedule_dict, descriptions_dict)               │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ Coordinator Updates Data                                    │
│   coordinator.data = (schedule, descriptions)               │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ├──────────────────┬──────────────────┬──────────────────┐
                  ▼                  ▼                  ▼                  ▼
         ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
         │ Individual   │   │ Today        │   │ Tomorrow     │   │ Next         │
         │ Sensors      │   │ Collection   │   │ Collection   │   │ Collection   │
         │ (per waste)  │   │ Sensor       │   │ Sensor       │   │ Sensor       │
         └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
```

### Entities Created

#### Individual Waste Type Sensors
- Created for **every** waste type from API
- Entity ID: `sensor.bio`, `sensor.resztkowe`, etc.
- State: Next collection date (`YYYY-MM-DD`)
- Attributes:
  - `next_date`: Next collection date
  - `days_until`: Days until next collection
  - `is_today`: Boolean
  - `is_tomorrow`: Boolean
  - `upcoming_dates`: List of next 3 dates
  - `all_dates`: All collection dates this year
  - `waste_type_id`: API ID
  - `color`: Hex color from API
  - `description`: Sorting instructions

#### Aggregate Sensors (based on selected types)
- `sensor.today_collection`: "Yes" or "No"
  - Attributes: `waste_types` (list), `count`
- `sensor.tomorrow_collection`: "Yes" or "No"
  - Attributes: `waste_types` (list), `count`
- `sensor.next_collection`: Next collection date
  - Attributes: `next_waste_type`, `waste_types` (list), `days_until`

#### Info Sensors (diagnostic)
- `sensor.schedule_last_change`: Date when schedule was modified (from API)
- `sensor.last_update`: Timestamp of last data fetch

#### Button
- `button.refresh_schedule`: Manual data refresh

## API Documentation

Base URL: `https://pluginecoapi.ecoharmonogram.pl/v1`

### 1. Get Towns for Community

```bash
curl -X GET 'https://pluginecoapi.ecoharmonogram.pl/v1/townsForCommunity?communityId=108'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "towns": [
      {
        "id": "2149",
        "name": "Gdańsk",
        "communityId": "108"
      }
    ]
  }
}
```

### 2. Get Schedule Periods

```bash
curl -X GET 'https://pluginecoapi.ecoharmonogram.pl/v1/schedulePeriodsWithDataForCommunity?communityId=108'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "schedulePeriods": [
      {
        "id": "8814",
        "startDate": "2025-01-01",
        "endDate": "2025-12-31",
        "changeDate": "2024-12-15"
      }
    ]
  }
}
```

### 3. Get Streets for Town

```bash
curl -X POST 'https://pluginecoapi.ecoharmonogram.pl/v1/streetsForTown' \
  -H 'Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW' \
  -H 'Origin: https://pluginv1.dtsolution.pl' \
  --data-raw $'------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name="townId"\r\n\r\n2149\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name="periodId"\r\n\r\n8814\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW--\r\n'
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "name": "Dzielna",
      "choosedStreetIds": "12345,67890"
    }
  ]
}
```

### 4. Get Building Groups

```bash
curl -X POST 'https://pluginecoapi.ecoharmonogram.pl/v1/streets' \
  -H 'Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW' \
  -H 'Origin: https://pluginv1.dtsolution.pl' \
  --data-raw $'------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name="choosedStreetIds"\r\n\r\n12345,67890\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name="number"\r\n\r\n6\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name="townId"\r\n\r\n2149\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name="streetName"\r\n\r\nDzielna\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name="schedulePeriodId"\r\n\r\n8814\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name="groupId"\r\n\r\n1\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW--\r\n'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "groups": {
      "items": [
        {
          "name": "Zabudowa jednorodzinna",
          "choosedStreetIds": "23868396"
        }
      ]
    }
  }
}
```

### 5. Get Waste Schedule (Main Endpoint)

```bash
curl -X POST 'https://pluginecoapi.ecoharmonogram.pl/v1/schedules' \
  -H 'Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW' \
  -H 'Origin: https://pluginv1.dtsolution.pl' \
  --data-raw $'------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name="number"\r\n\r\n6\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name="streetId"\r\n\r\n23868396\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name="townId"\r\n\r\n2149\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name="streetName"\r\n\r\nDzielna\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name="schedulePeriodId"\r\n\r\n8814\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name="lng"\r\n\r\npl\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW--\r\n'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "scheduleDescription": [
      {
        "id": "85873",
        "name": "BIO",
        "color": "#ae6f46",
        "description": "Informacje jak sortować odpady...",
        "typeId": "1",
        "order": "1",
        "month": "1",
        "year": "2025",
        "days": "2;9;16;23;30",
        "scheduleDescriptionId": "85873"
      },
      {
        "id": "85874",
        "name": "RESZTKOWE",
        "color": "#303030",
        "description": "Informacje jak sortować odpady...",
        "typeId": "2",
        "order": "2",
        "month": "1",
        "year": "2025",
        "days": "8;21",
        "scheduleDescriptionId": "85874"
      },
      {
        "id": "85875",
        "name": "METALE I TWORZYWA SZTUCZNE",
        "color": "#ffff00",
        "description": "Informacje jak sortować odpady...",
        "typeId": "13",
        "order": "3",
        "month": "1",
        "year": "2025",
        "days": "15",
        "scheduleDescriptionId": "85875"
      }
    ]
  }
}
```

**Note:** The API response structure has all schedule data and descriptions combined in the `scheduleDescription` array. Each entry contains both the waste type information and the collection dates for that month.

## Configuration Storage

Configuration is stored in Home Assistant's config entry with these keys:

```python
CONF_COMMUNITY_ID = "community_id"          # "108"
CONF_TOWN_ID = "town_id"                    # "2149"
CONF_TOWN_NAME = "town_name"                # "Gdańsk"
CONF_PERIOD_ID = "period_id"                # "8814"
CONF_PERIOD_START = "period_start"          # "2025-01-01"
CONF_PERIOD_END = "period_end"              # "2025-12-31"
CONF_PERIOD_CHANGE_DATE = "period_change_date"  # "2024-12-15"
CONF_STREET_NAME = "street_name"            # "Dzielna"
CONF_STREET_CHOOSED_IDS = "street_choosed_ids"  # "12345,67890"
CONF_NUMBER = "number"                      # "6"
CONF_STREET_ID = "street_id"                # "23868396"
CONF_GROUP_NAME = "group_name"              # "Zabudowa jednorodzinna"
CONF_SELECTED_WASTE_TYPES = "selected_waste_types"  # ["85873", "85874"]
```

## Update Schedule

Data is updated:
1. **Daily at 00:01** - Scheduled via `async_track_time_change` in `__init__.py`
2. **On Home Assistant restart** - Via `async_config_entry_first_refresh`
3. **Manual refresh** - Via refresh button triggering `coordinator.async_request_refresh()`

## Data Structure

### Schedule Dictionary
```python
schedule = {
    "BIO": [
        datetime(2025, 1, 2),
        datetime(2025, 1, 9),
        datetime(2025, 1, 16),
        # ...
    ],
    "RESZTKOWE": [
        datetime(2025, 1, 8),
        datetime(2025, 1, 21),
        # ...
    ]
}
```

### Descriptions Dictionary
```python
descriptions = {
    "BIO": {
        "id": "85873",
        "color": "#ae6f46",
        "description": "Informacje jak sortować odpady...",
        "type_id": "1",
        "order": "1"
    },
    "RESZTKOWE": {
        "id": "85874",
        "color": "#303030",
        "description": "Informacje jak sortować odpady...",
        "type_id": "2",
        "order": "2"
    },
    "METALE I TWORZYWA SZTUCZNE": {
        "id": "85875",
        "color": "#ffff00",
        "description": "Informacje jak sortować odpady...",
        "type_id": "13",
        "order": "3"
    }
}
```

## CMG Gdańsk Official Colors

Based on actual API responses from CMG Gdańsk:

| Waste Type | Polish Name | Color Code | RGB | Visual |
|------------|-------------|------------|-----|--------|
| Plastic & Metal | METALE I TWORZYWA SZTUCZNE | `#ffff00` or `#fed000` | Yellow | 🟨 |
| Paper | PAPIER | `#009fe3` | rgb(0, 159, 227) | 🟦 Light Blue |
| Glass | SZKŁO | `#3aaa35` | rgb(58, 170, 53) | 🟩 Green |
| Mixed | RESZTKOWE | `#303030` | rgb(48, 48, 48) | ⬛ Dark Gray |
| BIO | BIO | `#ae6f46` | rgb(174, 111, 70) | 🟫 Brown |
| Bulky | WIELKOGABARYTY | `#c0c0c0` | rgb(192, 192, 192) | ⬜ Light Gray |
| Payment Dates | TERMINY PŁATNOŚCI | `#ff0000` | rgb(255, 0, 0) | 🟥 Red |

## API Parsing Logic

The API returns a combined structure where each `scheduleDescription` entry contains both:
- Waste type information (id, name, color, description)
- Schedule data for that specific month (month, year, days)

The parser:
1. Groups entries by waste type name
2. Extracts waste type metadata (color, description, etc.)
3. Parses all date entries for each waste type
4. Sorts dates chronologically
5. Filters by selected waste types if provided

Example parsing flow:
```
API Response:
  scheduleDescription[0]: BIO, January, days: "2;9;16"
  scheduleDescription[1]: BIO, February, days: "6;13;20"
  scheduleDescription[2]: RESZTKOWE, January, days: "8;21"

Parsed Result:
  BIO: [2025-01-02, 2025-01-09, 2025-01-16, 2025-02-06, ...]
  RESZTKOWE: [2025-01-08, 2025-01-21, ...]
```

## Error Handling

- **API errors**: Cached data is used if available, otherwise `UpdateFailed` exception
- **Missing data**: Sensors show `None` state with empty attributes
- **Configuration errors**: Clear error messages in config flow

## Debugging

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.waste_collection: debug
```

## API Rate Limiting

- No configurable update interval to avoid API overload
- Updates only at midnight, restart, or manual refresh
- API client uses session for connection pooling
- Responses are cached in coordinator

## Localization

Supported languages:
- English (`strings.json`)
- Polish (`translations/pl.json`)

All entity names, descriptions, and config flow text are translated.