# Priority Matrix

| Priority | Use when |
|---|---|
| **P0** | Production-down for the customer (cannot use the product at all), security incident, data loss reported |
| **P1** | Major feature broken, business-blocking but workaround exists; OR repeat issue from a high-revenue customer ($10k+ ARR); OR customer mentions board/exec impact |
| **P2** | Feature partially broken, single-user impact, paying customer, not blocking; OR account access issues for active users |
| **P3** | Question, clarification, feature request, cosmetic bug, free-tier user, or non-urgent request |

Priority can be raised one level if the customer's `lifetime_revenue_usd` > $20,000 or `past_30d_tickets_count` > 4. Never raise priority based on tone alone — angry tone is not a priority signal, business impact is.
