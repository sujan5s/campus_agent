**Deterministic components: validation accuracy**

| Component | Cases | Valid accepted | Invalid rejected | Correct | Median time |
| --- | --- | --- | --- | --- | --- |
| Constraint registry validator | 30 (14/14 kinds) | 15/15 | 15/15 | 30/30 | < 0.01 ms |
| Assistant op compiler | 20 | 12/12 | 8/8 | 20/20 | 5.25 ms |
| Facility venue resolution | 20 | – | – | 19/20 | 0.67 ms |
| Degradation (LLM outage) | 100 | – | – | 100/100 answered, 0 exceptions | 0.17 ms |
