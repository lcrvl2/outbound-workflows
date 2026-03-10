# Workflow Configurations

Saved parameter presets for different campaigns. Copy and modify for new campaigns.

---

## 2025-09 Growth Squad: Social Media Roles (NA)

```yaml
source_list: "NEW 2025-09 Growth Squad: Companies Hiring Social Media Positions (DMs)"
destination_people_list: "NEW 2025-09 Growth Squad: Final People List Companies Hiring Social Media Roles"
owner_rep: "[NA Rep Name]"  # TODO: Fill in after first run
sequence_name: "2025-09 Growth Squad: EN Companies Hiring Social Media Roles Email Sequence"
sf_campaign: "2025 Growth Squad - Intent Job Hire Campaign (Parent)"
suppression_company_list: "2025-09 Growth Squad - Companies Hiring Social Media Roles List"
mode: "interactive"  # Change to "autonomous" after validation
```

**Notes**:
- NA only for now (single rep)
- Run weekly

---

## Template: New Campaign Config

```yaml
source_list: ""
destination_people_list: ""
owner_rep: ""
sequence_name: ""
sf_campaign: ""
suppression_company_list: ""
mode: "interactive"
```

---

## Region Mapping (Future)

When expanding beyond NA:

```yaml
region_mapping:
  NA:
    rep: "[NA Rep Name]"
    countries: ["United States", "Canada"]
  EMEA:
    rep: "[EMEA Rep Name]"
    countries: ["United Kingdom", "Germany", "France", ...]
  APAC:
    rep: "[APAC Rep Name]"
    countries: ["Australia", "Japan", "Singapore", ...]
```

Contact region determined by: [Company HQ location / Contact country - TBD]
