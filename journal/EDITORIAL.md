# Caretaker Journal: editorial guide

Find the people, research and inventions that make a world of repair more possible. Write for curious owners and practical builders, in a human, hopeful, concrete voice.

## Editorial lens

Connect new research, reporting, companies and open projects to a recognisable machine or repair problem. What happened? Why does it matter? What might it unlock for a vehicle, bicycle, boat or beloved appliance? What could the Caretaker community try?

Prefer original reporting, papers, project repositories and company primary sources, corroborated by independent reporting when possible. Link directly to sources near claims. Separate demonstrations from plans, comparisons from speculation, and real-world results from simulated results. Represent failures and limitations fairly. Credit the people and projects involved; don't imply endorsement or claim Caretaker has capabilities it hasn't built.

Write one genuinely useful original article when there is enough evidence. Avoid filler, copied material, invented quotes, SEO keyword stuffing and repeated topics. Do not publish if credible evidence is insufficient. Do not include private user data. Include a clear title, a concise description, the date, a relevant link to the open-source project, and a specific invitation to contribute.

## Publishing

Create a Markdown file under `_posts/YYYY-MM-DD-descriptive-slug.md`. Use Jekyll front matter:
```yaml
---
layout: post
title: "Clear descriptive title"
description: "A concise, accurate summary for search and sharing."
---
```

The date in the filename provides the publication date. The journal index, home page, sitemap and feed are generated automatically by GitHub Pages on build. Confirm a new build succeeded and verify the public URL where possible. If Pages is disabled or publication fails, retain the article in the repository and report the blocker rather than claiming it is live or indexed. Search indexing is not guaranteed.
