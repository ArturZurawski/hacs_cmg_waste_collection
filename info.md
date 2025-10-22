# Czyste Miasto Gdańsk - Waste Collection

Home Assistant integration for waste collection schedules in Gdańsk from Czyste Miasto Gdańsk.

## ✨ Features

- 🗑️ **Sensors for each waste type** - BIO, MIXED, PAPER, METALS, GLASS, BULKY
- 📅 **Aggregate sensors** - Know if collection is today or tomorrow
- 🎨 **CMG colors** - Each type uses official bin colors
- 🔄 **Refresh button** - Manual data fetch from API
- ⏰ **Auto-update** - Daily at midnight
- 🌍 **Bilingual** - Polish and English

## 📦 Installation

**Manual installation (not yet in HACS store):**

1. Open HACS → **Integrations** → **⋮** (top right) → **Custom repositories**
2. Add repository URL: `https://github.com/ArturZurawski/hacs_cmg_waste_collection`
3. Category: **Integration**
4. Click **Add**
5. Find **"Czyste Miasto Gdańsk"** in HACS and click **Download**
6. Restart Home Assistant
7. Go to **Settings** → **Devices & services** → **Add Integration**
8. Search: **"Czyste Miasto Gdańsk"**
9. Follow the 7-step configuration wizard

## 🎯 Configuration

The wizard guides you through:

1. **Community ID** - Default 108 for Gdańsk
2. **Town** - Select from list (e.g., Gdańsk)
3. **Schedule period** - Auto-filtered by year
4. **Street** - Search by name
5. **Building number** - Your address
6. **Building type** - Single/Multi-family/Business
7. **Waste type selection** - Which waste to monitor in aggregate sensors

## 📊 Created Sensors

### Individual waste type sensors

Each sensor shows **next collection date**:

- `sensor.bio` - Biodegradable waste
- `sensor.resztkowe` - Mixed waste
- `sensor.papier` - Paper and cardboard
- `sensor.metale_i_tworzywa_sztuczne` - Metals and plastics
- `sensor.szklo` - Glass
- `sensor.wielkogabaryty` - Bulky waste
- `sensor.terminy_platnosci` - Payment dates (if available)

**Each sensor attributes:**
- `next_date` - Next collection date
- `days_until` - Days until collection
- `is_today` - Is today
- `is_tomorrow` - Is tomorrow
- `color` - Bin color (hex)
- `upcoming_dates` - Next 3 dates
- `all_dates` - All dates this year

### Aggregate sensors

- `sensor.today_collection` - **"Yes"** or **"No"**
  - `waste_types` - List of types collected today
  - `monitored_types` - All monitored types

- `sensor.tomorrow_collection` - **"Yes"** or **"No"**
  - `waste_types` - List of types collected tomorrow
  - `monitored_types` - All monitored types

- `sensor.next_collection` - **Next collection date**
  - `next_waste_type` - Main type
  - `waste_types` - All types on this day
  - `days_until` - Days until

### Diagnostic sensors

- `sensor.last_update` - Last API data fetch
- `sensor.schedule_last_change` - Last schedule change by CMG

### Button

- `button.refresh_schedule` - Fetch data now (don't wait until midnight)

## 🎨 CMG Official Colors

Each sensor has a `color` attribute with hex code matching official bin colors:

- **BIO** - `#ae6f46` (brown) 🟫
- **MIXED** - `#9d9d9c` (gray) ⬛
- **PAPER** - `#009fe3` (blue) 🟦
- **METALS & PLASTICS** - `#fed000` (yellow) 🟨
- **GLASS** - `#3aaa35` (green) 🟩
- **BULKY** - `#d1d1d1` (light gray) ⬜
- **PAYMENT DATES** - `#E30000` (red) 🟥

## 💡 Usage Examples

### Card with upcoming collections

```yaml
type: entities
title: 🗑️ Waste Schedule
entities:
  - sensor.today_collection
  - sensor.tomorrow_collection
  - type: divider
  - sensor.bio
  - sensor.resztkowe
  - sensor.papier
  - sensor.metale_i_tworzywa_sztuczne
  - sensor.szklo
```

### Automation - evening reminder

```yaml
automation:
  - alias: "Waste - evening reminder"
    trigger:
      - platform: time
        at: "20:00:00"
    condition:
      - condition: state
        entity_id: sensor.tomorrow_collection
        state: "Yes"
    action:
      - service: notify.mobile_app
        data:
          title: "🗑️ Waste collection tomorrow!"
          message: "{{ state_attr('sensor.tomorrow_collection', 'waste_types') | join(', ') }}"
```

## 🔗 Links

- [Documentation](https://github.com/ArturZurawski/hacs_cmg_waste_collection)
- [CMG Gdańsk](https://czystemiasto.gdansk.pl/)

## 📄 License

MIT

## 🙏 Credits

Data provided by [Czyste Miasto Gdańsk](https://czystemiasto.gdansk.pl/)