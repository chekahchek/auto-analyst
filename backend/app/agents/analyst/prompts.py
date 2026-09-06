import re


PLOTLY_FIGURE_TOKEN_TEMPLATE = "__PLOTLY_FIGURE_{index}__"
PLOTLY_FIGURE_TOKEN = re.compile(
    re.escape(PLOTLY_FIGURE_TOKEN_TEMPLATE).replace(
        re.escape("{index}"), r"(\d+)"
    )
)


# Format for the output of hypotheses generation
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
- **Save each figure to a JSON file** in the figures directory given in your system prompt (e.g. `fig_0.json`) using `json.dump(fig, f, cls=plotly.utils.PlotlyJSONEncoder)`. Reference the file by its absolute path in the chart's `figure` field — never inline the full figure JSON.
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
      "figure": "/absolute/path/to/figures/fig_0.json"
    }
  ]
}
```

## Output Structure

Your final response must be a single, parseable JSON object.

### Agent Response Format

Pass a single JSON object as the `hypotheses_evidence` argument. Do not wrap it in markdown code blocks or add any prose.

```json
{
  "hypotheses_evidence": {
    "insights": [
      "The top 10% of customers by spend account for 54% of total revenue...",
      "Group A's higher average is driven by 3 extreme rows; the median is nearly identical to Group B's..."
    ],
    "charts": [
      {
        "title": "Revenue Share by Customer Decile",
        "insight_index": 0,
        "description": "Top 10% of customers by spend drive 54% of total revenue",
        "figure": "/absolute/path/to/figures/fig_0.json"
      }
    ]
  }
}
```

### Field Definitions

- **`insights`** — array of strings. Each insight should be self-contained, quantified, and ready for a storytelling node to consume directly. Avoid heavy markdown formatting. Any verbatim text snippet embedded in an insight must be short (a few words) and free of PII.
- **`charts`** — array of objects, each containing:
  - `title` — chart title string
  - `insight_index` — zero-based index into the `insights` array that this chart supports
  - `description` — brief description of what the chart shows
  - `figure` — the absolute path to the saved Plotly figure JSON file (do NOT inline the figure JSON here)

### What NOT to include

- No monolithic markdown report, no "Summary" section, no "Open Questions" section.
- No markdown fences around the JSON.
- Do NOT include a section-by-section audit of what you checked and didn't check. The user cares about insights, not your process.
- Do NOT include raw, unredacted verbatim passages of any length that could leak PII.

Keep the tone analytical but accessible. The user may not be a statistician — translate technical findings into business language.
"""


ANALYST_SYSTEM_PROMPT_TEMPLATE = (
    "You are an expert in data analysis. You are given a path to a dataset as well as what category "
    "the data belongs to.\n"
    "Dataset path: {dataset_path}\n"
    "Data category: {data_type}\n"
    "Figures directory: {figures_dir}\n\n"
    "Your job is to analyse the dataset using available tools and generate comprehensive insights from "
    "them. Begin by loading up the relevant skill based on the category before analysing it. You must "
    "adhere to the output instructions provided in the skill instructions.\n"
    "If the user is asking a general or conversational question that does not require analysing the "
    "dataset, answer directly without tools or skills.\n"
    "If you cannot answer from existing context, call the relevant tool in this same turn. Never end "
    "your turn with just a description of what you plan to do next or return some internal thought."
    "E.g. I need to investigate this data.\n"
    "When you create a chart, save its Plotly figure to a JSON file inside the figures directory "
    "(e.g. '{figures_dir}/fig_0.json') using `json.dump(fig, f, cls=plotly.utils.PlotlyJSONEncoder)`, "
    "then set that chart's `figure` field to the file's absolute path. Never inline the full figure "
    "JSON into the submit tool call.\n"
    "When you are ready to submit your final insights, use the `submit_hypotheses_evidence` tool. If "
    "the user asked you to edit the existing dashboard, submit the full edited HTML via the "
    "`update_dashboard_html` tool instead."
)

# Follow up context is appended to analyst system prompt if there are previous analysis artifacts
FOLLOW_UP_CONTEXT_TEMPLATE = (
    "A previous analysis already exists for this conversation. Use it to answer follow-up questions "
    "directly; only run a new analysis if the question cannot be answered from it.\n"
    "If you do need to re-analyse or edit the dashboard, call the relevant tool in this same turn; "
    "never just describe what you will do next.\n\n"
    "{context}"
)

STORYTELLER_SKILL_ID = "core/storytelling"


STORYTELLER_PROMPT_TEMPLATE = (
    "You are an expert in storytelling. You have been given a set of insights from a data analysis "
    "performed by an analyst agent.\n"
    "Your job is to create a compelling narrative that communicates these insights effectively.\n"
    "The skill instructions below provide guidance on how to structure the narrative:\n"
    "{skill_instructions}"
)

FRONTEND_DESIGNER_SKILL_ID = "core/frontend-design"


FRONTEND_DESIGNER_PROMPT_TEMPLATE = (
    "You are an expert frontend designer and dashboard builder. You have been given a structured "
    "narrative from a storyteller agent, including the chart titles and descriptions.\n"
    "The skill instructions below provide guidance on distinctive, intentional visual design:\n"
    "{skill_instructions}\n\n"
    "## Output contract\n"
    "Build ONE complete HTML document that renders the narrative as a single-page "
    "dashboard.\n"
    "- Return ONLY the HTML source. Do not wrap it in markdown code fences and do not add any prose "
    "before or after it.\n"
    "- Load Plotly.js from a CDN in the <head>.\n"
    f"- For every chart referenced in the slides, place the exact token "
    f"`{PLOTLY_FIGURE_TOKEN_TEMPLATE.format(index='<index>')}` where the chart should appear "
    f"(e.g. `{PLOTLY_FIGURE_TOKEN_TEMPLATE.format(index=0)}`). Charts are referenced by zero-based "
    "index into the narrative's `charts` array. Do not write any `Plotly.newPlot` call or figure JSON "
    "yourself — a build step replaces each token with a reference to the existing figure file. Do not "
    "invent or emit server filesystem paths.\n"
    "- Every text block from the narrative slides must appear in the page. Charts are referenced by "
    "zero-based index into the narrative's `charts` array; each referenced chart must be rendered.\n"
    "- Keep all CSS inline. Plotly.js from a CDN is the only required external dependency; you may "
    "load web fonts via <link> when they carry the design. Figure data is supplied by the build step.\n"
    "- The page must be responsive down to mobile, with visible keyboard focus and "
    "`prefers-reduced-motion` respected.\n"
)
