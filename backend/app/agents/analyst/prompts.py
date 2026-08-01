OUTPUT_FORMAT_INSTRUCTIONS = """\
## What Makes an Insight Worth Surfacing

A good insight passes at least two of these tests:

1. **Quantified** — "The top 10% of customers by spend account for 54% of total revenue" not "some customers spend more."
2. **Surprising or non-obvious** — contradicts intuition, reveals a hidden pattern, or explains a mystery.
3. **Actionable or decision-relevant** — informs a decision, flags a risk, or reveals an opportunity.
4. **Root-caused** — explains *why*, not just *what*. "Group A's average is higher only because of 3 extreme rows; the median is nearly identical to Group B's."

### Suggested Themes (aim for variety)

Aim for 5–10 insights covering different angles — pick the strongest, not one from every lens:
- Distribution shape / skew
- Strong (or suspiciously absent) relationship between variables
- Group comparison
- Outlier-driven finding
- Missingness pattern
- Concentration / composition
- Data quality observation or methodological caution

### Format for Each Insight

```
- **[Theme]**: [Quantified finding]. [Context / root cause]. [Implication or question].
```

**Example:**
```
- **Revenue concentration**: The top 10% of customers by spend account for 54% of total revenue, while the bottom 50% contribute just 9%. This is driven almost entirely by the Enterprise segment (avg. spend 8x Self-Serve) — treating all customers as one population understates how dependent revenue is on a small group.
```

## When to Generate a Chart

Ask yourself: *would a chart make this insight significantly easier to grasp?* If no, skip it.

### Requirements

- **Use Plotly** (not matplotlib or seaborn). Plotly figures are native JavaScript objects that render directly in HTML via `Plotly.newPlot()`.
- **Return chart data as Plotly figure JSON specs** (standard `fig.to_dict()` output).
- **Make charts interactive and well-labeled:** clear titles, axis labels, legends, and hover tooltips. Avoid clutter.
- **Match chart type to insight.** Common mappings:
  - Distribution / skew → histogram or box plot
  - Relationship between two numerics → scatter plot (with trend line if relevant)
  - Group comparison → bar chart or box plot per group
  - Concentration → sorted bar / Pareto chart
  - Missingness → bar chart of missing rate per column
  - Trend / level over time → line chart
  - Seasonality / periodic patterns → line chart with multiple series or grouped bar chart
  - Cross-section comparison → horizontal bar chart or small-multiples
  - Sentiment distribution / trend → histogram or line chart
  - Topic/theme sizes or keyword ranking → horizontal bar chart

### Chart Manifest

Each chart must include metadata so the storytelling and frontend nodes know which insight it belongs to:

```json
{
  "charts": [
    {
      "title": "Revenue Share by Customer Decile",
      "insight_index": 0,
      "description": "Top 10% of customers by spend drive 54% of total revenue",
      "figure": { /* Plotly figure JSON spec from fig.to_dict() */ }
    }
  ]
}
```

## Output Structure

Your final response must be a single, parseable JSON object.

### Agent Response Format

Return exactly one JSON object in the following shape. Do not wrap it in markdown code blocks or add any prose before or after it.

```json
{
  "insights": [
    "The top 10% of customers by spend account for 54% of total revenue...",
    "Group A's higher average is driven by 3 extreme rows; the median is nearly identical to Group B's..."
  ],
  "charts": [
    {
      "title": "Revenue Share by Customer Decile",
      "insight_index": 0,
      "description": "Top 10% of customers by spend drive 54% of total revenue",
      "figure": { /* Plotly figure JSON spec from fig.to_dict() */ }
    }
  ]
}
```

### Field Definitions

- **`insights`** — array of strings. Each insight should be self-contained, quantified, and ready for a storytelling node to consume directly. Avoid heavy markdown formatting. Any verbatim text snippet embedded in an insight must be short (a few words) and free of PII.
- **`charts`** — array of objects, each containing:
  - `title` — chart title string
  - `insight_index` — zero-based index into the `insights` array that this chart supports
  - `description` — brief description of what the chart shows
  - `figure` — the Plotly figure JSON spec (output of `fig.to_dict()`)

### What NOT to include

- No monolithic markdown report, no "Summary" section, no "Open Questions" section.
- No markdown fences around the JSON.
- Do NOT include a section-by-section audit of what you checked and didn't check. The user cares about insights, not your process.
- Do NOT include raw, unredacted verbatim passages of any length that could leak PII.

Keep the tone analytical but accessible. The user may not be a statistician — translate technical findings into business language.
"""