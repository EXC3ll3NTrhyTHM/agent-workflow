# Week 6 Evaluation Results

Corpus size at run time: 241 unique postings.

## Per-case results

| Case | Arm | Success | P@5 | Rounds | Wall (s) |
|---|---|---|---|---|---|
| python_backend | full | fail | 0.40 | 3 | 82.8 |
| python_backend | round1 | fail | 0.40 | 1 | 0.0 |
| python_backend | fallback | fail | 0.20 | 3 | 0.1 |
| react_frontend | full | fail | 0.20 | 3 | 70.9 |
| react_frontend | round1 | fail | 0.00 | 1 | 0.0 |
| react_frontend | fallback | fail | 0.20 | 3 | 0.1 |
| data_analyst | full | fail | 0.40 | 3 | 72.3 |
| data_analyst | round1 | fail | 0.40 | 1 | 0.0 |
| data_analyst | fallback | fail | 0.20 | 3 | 0.1 |
| devops_sre | full | PASS | 0.60 | 1 | 22.3 |
| devops_sre | round1 | PASS | 0.60 | 1 | 0.0 |
| devops_sre | fallback | PASS | 0.80 | 3 | 0.1 |
| ml_engineer | full | fail | 0.40 | 3 | 71.5 |
| ml_engineer | round1 | fail | 0.20 | 1 | 0.0 |
| ml_engineer | fallback | fail | 0.00 | 3 | 0.1 |
| mobile_dev | full | fail | 0.40 | 3 | 70.5 |
| mobile_dev | round1 | fail | 0.20 | 1 | 0.0 |
| mobile_dev | fallback | fail | 0.40 | 3 | 0.1 |
| security_engineer | full | fail | 0.20 | 3 | 72.8 |
| security_engineer | round1 | fail | 0.20 | 1 | 0.0 |
| security_engineer | fallback | fail | 0.20 | 3 | 0.1 |
| data_engineer | full | fail | 0.20 | 3 | 150.7 |
| data_engineer | round1 | fail | 0.20 | 1 | 0.0 |
| data_engineer | fallback | fail | 0.00 | 3 | 0.1 |
| qa_automation | full | fail | 0.20 | 3 | 67.6 |
| qa_automation | round1 | fail | 0.20 | 1 | 0.0 |
| qa_automation | fallback | fail | 0.20 | 3 | 0.1 |
| product_manager | full | PASS | 0.60 | 3 | 82.9 |
| product_manager | round1 | PASS | 0.60 | 1 | 0.0 |
| product_manager | fallback | fail | 0.20 | 3 | 0.1 |
| technical_writer | full | fail | 0.00 | 3 | 61.5 |
| technical_writer | round1 | fail | 0.00 | 1 | 0.0 |
| technical_writer | fallback | fail | 0.00 | 3 | 0.1 |
| career_changer | full | fail | 0.20 | 3 | 80.8 |
| career_changer | round1 | fail | 0.20 | 1 | 0.0 |
| career_changer | fallback | fail | 0.00 | 3 | 0.1 |

## Summary

| Arm | Success rate | Mean P@5 | Mean rounds | Early-stop | Recovery |
|---|---|---|---|---|---|
| full | 17% | 0.32 | 2.8 | 8% | 1/11 |
| round1 | 17% | 0.27 | 1.0 | 0% | 1/11 |
| fallback | 8% | 0.20 | 3.0 | 0% | n/a |

## Failure categories (judged non-relevant postings)

- non-engineering: 136
- wrong-role-family: 87
- adjacent-stack: 24
- too-generic: 19
- seniority-mismatch: 11
- other: 3
