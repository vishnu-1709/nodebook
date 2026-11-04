<!-- prompt: recall_judge · version: 1 -->
## system
A student is rebuilding a mind map from memory: for each position they typed a label.
Judge whether each typed label means the same topic as the expected label (synonyms, abbreviations,
reordered words and minor spelling mistakes count as the same; a different or broader/narrower topic
does not). Answer only from the provided labels and slide text.
Reply with JSON only, matching the given schema: one verdict per item, in order.

## user
Lecture: {{lecture}}

Items:
{{items}}
