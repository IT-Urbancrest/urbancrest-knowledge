---
id: resources.church-center.links
version: 1.0
status: published
priority: 100

title: Church Center Links
summary: Explains where official Church Center links are stored and how AI articles should reference them.

category:
  - resources

intent:
  primary: resource_lookup
  secondary:
    - Church Center
    - links

audience:
  - staff
  - ai

answer_style: reference
confidence: high

tags:
  - Church Center
  - registry
  - links
  - forms

search_terms:
  - Church Center links
  - Connect Card link
  - Baptism form link
  - Giving link
  - Small Groups link
  - Serving form link

resources:
  - church_center.connect_card
  - church_center.baptism
  - church_center.giving
  - church_center.prayer_request
  - church_center.small_groups
  - church_center.serving

related:
  - registry/church-center.yaml

last_updated: 2026-07-06
---

# Church Center Links

Official Church Center links are stored in `registry/church-center.yaml`.

Knowledge articles should reference resource IDs instead of duplicating URLs.

## Available Resource IDs

- `church_center.connect_card`
- `church_center.baptism`
- `church_center.giving`
- `church_center.prayer_request`
- `church_center.small_groups`
- `church_center.serving`

## Usage Rule

If a Church Center URL changes, update `registry/church-center.yaml` first.
