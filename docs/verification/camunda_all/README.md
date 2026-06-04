# Camunda all.bpmn Verification Results

- Input BPMN: `Camunda-all-main/merged_code/bpmn/all.bpmn`
- PNML: `docs/verification/camunda_all/camunda_all.pnml`
- Bounded model: `docs/verification/camunda_all/camunda_all_bounded.mcrl2`
- Bound: each place is limited to at most 1 token(s)
- Visualization limit: first 2000 generated states
- LTS SVG: `docs/verification/camunda_all/camunda_all_bounded_lts.svg`
- Summary SVG: `docs/verification/camunda_all/camunda_all_verification_summary.svg`
- Property backend: `lts2pbes + pbes2bool` over the generated partial bounded LTS.

## LTS

- Number of states: 2001
- Number of action labels: 12 (including a tau label)
- Number of transitions: 2000
- Number of state labels: 2001
- LTS is deterministic: yes
- This lts has no probabilistic states: yes

## Properties

| Property | Action | Result | Expected | Backend | Interpretation |
| --- | --- | --- | --- | --- | --- |
| Order reaches freight forwarder | `order_to_ffw` | true | true | `lts2pbes+pbes2bool` | Owner can publish order-to-ffw. |
| Customs clearance reaches terminal | `customs_clearance_to_terminal` | false | false | `lts2pbes+pbes2bool` | Not observed within the default 2000-state partial LTS; increase --max-lts-states or run a dedicated solver check for deeper reachability. |
| Container reaches owner | `ctn_to_owner` | false | false | `lts2pbes+pbes2bool` | Not observed within the default 2000-state partial LTS; increase --max-lts-states or run a dedicated solver check for deeper reachability. |
| Ship departure notification is reachable | `ship_departure_notification` | false | false | `lts2pbes+pbes2bool` | Not observed within the default 2000-state partial LTS; increase --max-lts-states or run a dedicated solver check for deeper reachability. |
| Payment is reachable | `payment` | false | false | `lts2pbes+pbes2bool` | Not observed within the default 2000-state partial LTS; increase --max-lts-states or run a dedicated solver check for deeper reachability. |
| Joined end is reachable | `a_end` | false | false | `lts2pbes+pbes2bool` | Not observed within the default 2000-state partial LTS; this full-system end is expected to require deeper exploration. |
| Order-to-FFW requires handle-order | `handle_order -> order_to_ffw` | true | true | `lts2pbes+pbes2bool` | No explored path publishes order-to-ffw before handle-order. |
| Order received requires order-to-FFW | `order_to_ffw -> order_received` | true | true | `lts2pbes+pbes2bool` | No explored path reaches order-received before order-to-ffw. |
| Gateway 0ujvw7r can precede gateway 1mop6g2 | `parallel_gateway_gateway_0ujvw7r -> parallel_gateway_gateway_1mop6g2` | true | true | `lts2pbes+pbes2bool` | The bounded LTS contains one behavior where gateway 0ujvw7r occurs before gateway 1mop6g2. |
| Gateway 1mop6g2 can precede gateway 0ujvw7r | `parallel_gateway_gateway_1mop6g2 -> parallel_gateway_gateway_0ujvw7r` | true | true | `lts2pbes+pbes2bool` | The bounded LTS also contains the reverse order, so observers must not assume a fixed order between these parallel gateway effects. |

## Customs Scenario Targeted Witnesses

| Action | Result | State index | Backend | Interpretation |
| --- | --- | --- | --- | --- |
| manifest_received | true | 172 | `lps2lts --action --trace=1 --strategy=depth` | One of the three customs synchronization inputs is reachable with targeted depth-first exploration. |
| ctn_and_ship_arrive | true | 202 | `lps2lts --action --trace=1 --strategy=depth` | The terminal arrival input for the customs synchronization point is reachable. |
| declaration_received | true | 172 | `lps2lts --action --trace=1 --strategy=depth` | The broker declaration input for the customs synchronization point is reachable. |
| clearance_to_broker | true | 177 | `lps2lts --action --trace=1 --strategy=depth` | The broker-facing customs clearance response is reachable. |
| inspection_appointment | true | 181 | `lps2lts --action --trace=1 --strategy=depth` | The broker-side follow-up after customs clearance-to-broker is reachable. |
| ciq | true | 204 | `lps2lts --action --trace=1 --strategy=depth` | After the customs synchronization point, CIQ can execute. |
| inspection | true | 205 | `lps2lts --action --trace=1 --strategy=depth` | The customs inspection step after CIQ can execute. |
| customs_clearance_to_terminal | true | 206 | `lps2lts --action --trace=1 --strategy=depth` | The terminal-facing customs clearance output is reachable with targeted depth-first exploration. |
