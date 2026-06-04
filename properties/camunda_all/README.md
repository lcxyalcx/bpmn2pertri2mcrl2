# Camunda all.bpmn Properties

These formulas target the bounded mCRL2 model generated from
`Camunda-all-main/merged_code/bpmn/all.bpmn`.

The model abstracts Camunda variables and `orderId` values away. Message
correlation is represented by Petri-net message places, so each property checks
control-flow or message-synchronization reachability through generated action
names.

The default `check_camunda_all.py` run solves the core reachability formulas
with `lts2pbes + pbes2bool` over the generated partial bounded LTS, which is
fast and reproducible but still limited by the configured LTS state bound for
deep full-system properties.

Additional formulas in this directory cover two guide-relevant concerns:

- message causality safety, for example `order_to_ffw` cannot occur before
  `handle_order`, and `order_received` cannot occur before `order_to_ffw`;
- bounded parallel gateway order evidence, showing that two gateway actions can
  occur in either order in the explored state space.

Run:

```bash
python scripts/check_camunda_all.py
```
