# urbancrest-ai
Comprehensive knowledge base for agentic AI search &amp; digital tools for Urbancrest Church

# Urbancrest Church AI Knowledge Base

Welcome to the Urbancrest Church AI Knowledge Base. This repository serves as the single source of truth for the information used by Urbancrest's AI assistant, website, and future digital platforms.

The goal of this repository is to provide accurate, biblically sound, and up-to-date information so that people can easily find answers about our church, ministries, beliefs, events, and next steps.

---

# Purpose

This repository is designed to:

* Provide trusted information for AI-powered search and chat.
* Maintain consistent answers across the website and future applications.
* Allow staff to update information through version-controlled documentation.
* Organize church knowledge in a format that is easy for both humans and AI to understand.

---

# Repository Structure

```text
knowledge/
│
├── beliefs/
│   ├── salvation.md
│   ├── baptism.md
│   ├── communion.md
│   └── scripture.md
│
├── ministries/
│   ├── kids.md
│   ├── students.md
│   ├── men.md
│   ├── women.md
│   ├── missions.md
│   └── worship.md
│
├── next-steps/
│   ├── connect-card.md
│   ├── membership.md
│   ├── serve.md
│   └── small-groups.md
│
├── faq/
│   ├── giving.md
│   ├── service-times.md
│   ├── childcare.md
│   ├── parking.md
│   └── contact.md
│
├── sermons/
│   ├── summer-on-the-mount/
│   └── archived/
│
├── events/
│
├── staff/
│
└── policies/
```

---

# Writing Standards

All documents should be written in Markdown and begin with YAML front matter.

Example:

```yaml
---
title: Baptism
description: Answers common questions about baptism at Urbancrest Church.
category: Beliefs
subcategory: Ordinances
tags:
  - baptism
  - believer's baptism
  - immersion
  - salvation
search_terms:
  - How do I get baptized?
  - What is baptism?
  - Infant baptism
audience: everyone
last_updated: 2026-07-01
related:
  - salvation.md
---
```

---

# Document Guidelines

Each document should:

* Answer one topic thoroughly.
* Use headings to organize content.
* Write in clear, conversational language.
* Be optimized for AI retrieval.
* Include common questions people are likely to ask.
* Reference Scripture when appropriate.
* Reflect the doctrine and ministry philosophy of Urbancrest Church.

---

# FAQ Format

Whenever possible, organize information using question-and-answer formatting.

Example:

```markdown
## How do I get baptized?

Anyone who has placed their faith in Jesus Christ should be baptized by immersion as an act of obedience and a public profession of faith.

The first step is to complete the Baptism Interest Form.
```

Question-and-answer formatting improves retrieval accuracy for AI systems.

---

# Sermon Documents

Each sermon should include:

* Title
* Speaker
* Date
* Series
* Scripture
* Summary
* Main points
* Gospel emphasis
* Application
* AI tags

Avoid uploading raw transcripts unless necessary. Instead, create structured summaries that AI can search quickly.

---

# AI Tags

Each document should include relevant keywords and phrases that people are likely to search for.

Good examples:

* salvation
* baptism
* church membership
* giving
* connect card
* kids ministry
* service times
* prayer
* missions
* Small Groups

Include both ministry terminology and natural language phrases people might ask.

---

# Doctrinal Standard

All theological content should align with:

* The Bible as the inspired and authoritative Word of God.
* The Baptist Faith and Message 2000.
* The mission, vision, and values of Urbancrest Church.

When questions involve doctrine, answers should prioritize biblical truth while remaining gracious, clear, and accessible.

---

# Content Categories

This repository may include:

* Church beliefs
* Frequently asked questions
* Ministry information
* Events
* Sermon summaries
* Policies
* Staff information
* Next steps
* Giving
* Baptism
* Membership
* Volunteer opportunities
* Missions
* Church history
* Prayer resources

---

# Writing Style

Content should be:

* Biblically faithful
* Christ-centered
* Friendly and welcoming
* Concise
* Easy to understand
* Free of unnecessary jargon
* Optimized for both AI retrieval and human readers

Avoid ambiguous language or assumptions that require additional context.

---

# Updating Content

When making changes:

1. Update the Markdown file.
2. Review for biblical and factual accuracy.
3. Ensure tags and search terms remain relevant.
4. Update the `last_updated` field.
5. Commit changes with a descriptive message.

---

# Mission

Urbancrest Church exists to reach every nation and every street with one mission: helping people know Jesus, grow in faith, and live on mission together.

This repository exists to help our digital tools faithfully communicate that mission by providing trustworthy, consistent, and biblically grounded information to everyone who visits our website or interacts with our AI assistant.
