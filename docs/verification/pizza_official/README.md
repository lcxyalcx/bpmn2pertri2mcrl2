# Official Pizza Verification Results

- Bounded model: `docs/verification/pizza_official/pizza_official_bounded.mcrl2`
- Bound: each place is limited to at most 1 token(s)
- Visualization limit: first 200 generated states
- LTS SVG: `docs/verification/pizza_official/pizza_official_bounded_lts.svg`
- Summary SVG: `docs/verification/pizza_official/pizza_official_verification_summary.svg`

## LTS

- Number of states: 200
- Number of action labels: 18 (including a tau label)
- Number of transitions: 199
- Number of state labels: 200
- LTS is deterministic: yes
- This lts has no probabilistic states: yes

## Modal Formulas

| Property | Result | Expected | Interpretation |
| --- | --- | --- | --- |
| Order can reach vendor | true | true | After order_a_pizza, order_received remains possible. |
| Delivery is reachable | true | true | The vendor can bake and deliver the pizza. |
| Payment is reachable | true | true | The local PNML conversion lets payment consume the money message. |
| Ask/calm loop is reachable | true | true | The timeout/question/customer-calming loop can complete. |
| Joined end is reachable | true | true | Both participant processes can reach the joined end transition. |
| No deadlock | false | false | Deadlock is expected after both participant processes finish. |
