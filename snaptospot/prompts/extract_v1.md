# SnapToSpot extraction prompt — v1

You extract a campaign-ready content model from a website. The input is a JSON
object containing the site title, URL, page headings and text blocks. Every block
has a `source_id`.

Return one JSON object with exactly these keys:

```json
{
  "offerings": [
    {
      "key": "asr",
      "title": "Automatic speech recognition",
      "one_liner": "Whisper and wav2vec fine-tuned on Swahili, Sheng and code-switched audio.",
      "metric_fact_key": "asr.wer",
      "tools": ["Whisper", "wav2vec", "NeMo"],
      "source_ids": ["b12", "b13"]
    }
  ],
  "projects": [
    {
      "name": "SautiFlow",
      "blurb": "Script to voiced, mixed skit.",
      "badge_fact_key": "media.render_seconds",
      "status": "shipped",
      "source_ids": ["b31"]
    }
  ],
  "quote": {
    "text": "He rebuilt our narration pipeline and cut the bill by more than half.",
    "source_id": "b44",
    "attribution": "Daniel Reyes",
    "role": "Founder — Kite Learning",
    "permission": "published_on_site"
  },
  "metrics": [
    {
      "key": "asr.wer",
      "value": "11.8",
      "unit": "% WER",
      "label": "Swahili/Sheng ASR word error rate",
      "source_id": "b31",
      "source_quote": "11.8% word error rate, down from 23.4%"
    }
  ]
}
```

Rules, in order of importance:

1. **Quote, don't paraphrase, for numbers.** Every metric needs a `source_id`
   and a `source_quote` copied from that block. If you cannot quote it, omit it.
2. **Never invent a number, name, client, date or quote.** No value may be
   rounded, converted or computed. `60% faster` is not `2x faster`.
3. **Offerings**: at most 4. A title should come from a heading. The one-liner
   must be supported by the supplied text. Use no digits unless a supplied block
   contains them.
4. **Projects**: at most 8. Use real projects or case studies named on the site.
   Set `status` to `shipped`, `active`, `wip` or `archived` only when the text
   supports it; otherwise use `shipped`.
5. **Quote**: one named testimonial only. The text must be verbatim from a block,
   without the surrounding quotation marks. Include attribution only when the
   site names the person and role. `permission` is `published_on_site` for a quote
   already published on the site.
6. **Metrics**: at most 12. One fact per distinct claim. If a sentence compares
   two numbers, use the primary value and keep both in `source_quote`. Do not
   emit the baseline as a separate metric.
7. Return `null` or `[]` for anything unsupported. An empty section is correct.

Return JSON only. Do not wrap it in Markdown or add commentary.
