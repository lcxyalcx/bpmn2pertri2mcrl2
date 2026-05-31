# BPMN 基准样例覆盖报告

- 套件：`bpmn_benchmark_coverage_v3`
- 样例总数：11
- 兼容：11
- 不兼容：0

## 分类汇总

| 分类 | 总数 | 兼容 | 不兼容 |
| --- | ---: | ---: | ---: |
| `approximation` | 1 | 1 | 0 |
| `boundary-event` | 3 | 3 | 0 |
| `call-activity` | 1 | 1 | 0 |
| `collaboration` | 3 | 3 | 0 |
| `container-flattening` | 1 | 1 | 0 |
| `cross-pool` | 2 | 2 | 0 |
| `escalation-pattern` | 1 | 1 | 0 |
| `event-based` | 1 | 1 | 0 |
| `gateway` | 5 | 5 | 0 |
| `inclusive` | 1 | 1 | 0 |
| `interrupting` | 1 | 1 | 0 |
| `loop` | 1 | 1 | 0 |
| `message-flow` | 4 | 4 | 0 |
| `mixed-control-flow` | 3 | 3 | 0 |
| `multi-collaboration` | 1 | 1 | 0 |
| `multi-instance` | 1 | 1 | 0 |
| `nested-subprocess` | 2 | 2 | 0 |
| `non-interrupting` | 1 | 1 | 0 |
| `orchestration` | 1 | 1 | 0 |
| `parallel` | 3 | 3 | 0 |
| `subprocess` | 2 | 2 | 0 |
| `task-variation` | 1 | 1 | 0 |
| `transaction` | 2 | 2 | 0 |
| `xor` | 2 | 2 | 0 |

## 场景结果

| 场景 | 文件 | 重点 | 结果 | 备注 |
| --- | --- | --- | --- | --- |
| `gateway-xor-parallel-mix` | `examples/benchmarks/gateway_xor_parallel_mix.bpmn` | XOR + AND mixed routing | 兼容 | 0 warnings |
| `message-boundary-callactivity` | `examples/benchmarks/message_boundary_callactivity.bpmn` | messageFlow + boundaryEvent + callActivity/userTask | 兼容 | 0 warnings |
| `subprocess-transaction-nested` | `examples/benchmarks/subprocess_transaction_nested.bpmn` | subProcess + transaction + nested subProcess | 兼容 | 0 warnings |
| `gateway-xor-or-mix` | `examples/benchmarks/gateway_xor_or_mix.bpmn` | XOR + OR mixed routing | 兼容 | 0 warnings |
| `eventbased-parallel-mix` | `examples/benchmarks/eventbased_parallel_mix.bpmn` | eventBasedGateway + parallelGateway | 兼容 | 0 warnings |
| `cross-pool-message-loop` | `examples/benchmarks/cross_pool_message_loop.bpmn` | Cross-pool message loop with feedback/update cycle | 兼容 | 0 warnings |
| `boundary-parallel-escalation` | `examples/benchmarks/boundary_parallel_escalation.bpmn` | boundaryEvent + parallel escalation branch | 兼容 | 0 warnings |
| `nested-container-message-combo` | `examples/benchmarks/nested_container_message_combo.bpmn` | Nested containers + message dispatch | 兼容 | 0 warnings |
| `multi-instance-approximation` | `examples/benchmarks/multi_instance_approximation.bpmn` | multiInstanceLoopCharacteristics approximation handling | 兼容 | 1 warnings |
| `boundary-interrupt-modes` | `examples/benchmarks/boundary_interrupt_modes.bpmn` | Interrupting and non-interrupting boundary event combination | 兼容 | 0 warnings |
| `multi-collab-message-orchestration` | `examples/benchmarks/multi_collab_message_orchestration.bpmn` | Three-party message choreography across pools | 兼容 | 0 warnings |
