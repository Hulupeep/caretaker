---
layout: default
title: Keep the machines you love alive
description: "Caretaker is an open-source experiment in repairing and restoring the machines we love."
---

# Imagine never having to buy another car.

The van that carried your family to Italy. Your grandfather's motorbike. A boat waiting in a field. A 1950s mixer that still has stories to tell.

What if they could all have a caretaker?

We're exploring a future where people, sensors, software and robots work together to understand, maintain and repair the things we love. Start with one machine. Learn from what happens. Share the knowledge. Keep going.

**Caretaker is an open-source experiment—and you're invited.**

[Read the journal]({{ '/journal/' | relative_url }}) · [Bring your machine](https://github.com/Hulupeep/caretaker/issues/new?template=machine.yml) · [Explore the roadmap](https://github.com/Hulupeep/caretaker/blob/main/docs/visual-roadmap.md)

## Recent stories

{% for post in site.posts limit:3 %}
<div class="entry"><h2><a href="{{ post.url | relative_url }}">{{ post.title | escape }}</a></h2><p class="meta">{{ post.date | date: "%-d %B %Y" }}</p><p>{{ post.description | escape }}</p></div>
{% else %}
Our first research story is on its way.
{% endfor %}
