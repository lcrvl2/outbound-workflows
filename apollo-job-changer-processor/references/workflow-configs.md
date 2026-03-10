# Workflow Configurations

Saved parameter presets for job changer enrichment runs.

---

## 2026-02 Growth Squad: Job Changers - Current Users

```yaml
source_lists:
  EN:
    name: "2025-09 Growth Squad - Current Users Who Change Jobs"
    url: "https://app.apollo.io/#/lists/68a3d3b1d927eb000d5975c8"
  FR:
    name: "2025-09 Growth Squad - Current Users Who Change Jobs (FR)"
    url: "https://app.apollo.io/#/lists/68f9fd6aa4287600018c367d"
  DACH:
    name: "2025-09 Growth Squad - Current Users Who Change Jobs (DACH)"
    url: "https://app.apollo.io/#/lists/68f80e37de28c80011bb2d51"

enriched_list: "2026-02 Job changers intent - Global (ENRICHED)"
enriched_list_url: "https://app.apollo.io/#/lists/698217a1703af3002135f177"

sf_campaign: "2025 Growth Squad - Intent Job Changers Campaign (Parent)"

# Update contact pop-up settings
outdated_contact_stage: "new"
mark_sequences_finished: true

mode: "autonomous"
ui_validation: true
regions_to_process: ["EN", "FR", "DACH"]
```

**Notes**:
- All 3 regional lists feed into the same global enriched list
- Run weekly or as needed when job change updates accumulate
- EN list is typically the largest
- Switched to autonomous after successful interactive learning run (2026-02-09)

---

## Template: New Job Changer Config

```yaml
source_lists:
  EN:
    name: ""
    url: ""
  FR:
    name: ""
    url: ""
  DACH:
    name: ""
    url: ""

enriched_list: ""
enriched_list_url: ""

sf_campaign: ""

outdated_contact_stage: "new"
mark_sequences_finished: true

mode: "interactive"
ui_validation: true
regions_to_process: ["EN", "FR", "DACH"]
```
