# Evaluation Results

Corpus size at run time: 710 unique postings.

## Per-case results

| Case | Arm | Success | P@5 | Rounds | Wall (s) |
|---|---|---|---|---|---|
| python_backend | full | PASS | 1.00 | 2 | 37.4 |
| python_backend | round1 | PASS | 0.80 | 1 | 0.0 |
| python_backend | fallback | PASS | 0.60 | 2 | 0.1 |
| react_frontend | full | PASS | 1.00 | 2 | 25.3 |
| react_frontend | round1 | PASS | 1.00 | 1 | 0.0 |
| react_frontend | fallback | PASS | 0.80 | 2 | 0.2 |
| data_analyst | full | PASS | 0.80 | 3 | 47.0 |
| data_analyst | round1 | PASS | 0.60 | 1 | 0.0 |
| data_analyst | fallback | PASS | 0.60 | 2 | 0.2 |
| devops_sre | full | PASS | 1.00 | 1 | 22.9 |
| devops_sre | round1 | PASS | 1.00 | 1 | 0.0 |
| devops_sre | fallback | PASS | 1.00 | 2 | 0.1 |
| ml_engineer | full | PASS | 1.00 | 1 | 26.4 |
| ml_engineer | round1 | PASS | 1.00 | 1 | 0.0 |
| ml_engineer | fallback | PASS | 0.80 | 2 | 0.1 |
| mobile_dev | full | fail | 0.20 | 2 | 38.1 |
| mobile_dev | round1 | fail | 0.00 | 1 | 0.0 |
| mobile_dev | fallback | fail | 0.20 | 2 | 0.2 |
| security_engineer | full | PASS | 0.60 | 1 | 18.4 |
| security_engineer | round1 | PASS | 0.60 | 1 | 0.0 |
| security_engineer | fallback | PASS | 0.60 | 2 | 0.1 |
| data_engineer | full | fail | 0.20 | 3 | 31.9 |
| data_engineer | round1 | fail | 0.20 | 1 | 0.0 |
| data_engineer | fallback | fail | 0.00 | 2 | 0.1 |
| qa_automation | full | PASS | 0.60 | 3 | 50.4 |
| qa_automation | round1 | fail | 0.40 | 1 | 0.0 |
| qa_automation | fallback | fail | 0.40 | 2 | 0.1 |
| product_manager | full | PASS | 1.00 | 2 | 30.7 |
| product_manager | round1 | PASS | 1.00 | 1 | 0.0 |
| product_manager | fallback | PASS | 0.80 | 2 | 0.1 |
| technical_writer | full | fail | 0.00 | 2 | 34.7 |
| technical_writer | round1 | fail | 0.00 | 1 | 0.0 |
| technical_writer | fallback | fail | 0.00 | 2 | 0.1 |
| career_changer | full | fail | 0.40 | 3 | 60.1 |
| career_changer | round1 | fail | 0.00 | 1 | 0.0 |
| career_changer | fallback | fail | 0.00 | 2 | 0.1 |

## Summary

| Arm | Success rate | Mean P@5 | Mean rounds | Early-stop | Recovery |
|---|---|---|---|---|---|
| full | 67% | 0.65 | 2.1 | 67% | 5/9 |
| round1 | 58% | 0.55 | 1.0 | 0% | 4/9 |
| fallback | 58% | 0.48 | 2.0 | 100% | n/a |

## Failure categories (judged non-relevant postings)

- non-engineering: 88
- wrong-role-family: 70
- adjacent-stack: 27
- seniority-mismatch: 7
- other: 3
- too-generic: 2
