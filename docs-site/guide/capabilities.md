# System capabilities

The system deploys a vision-language-action model across resource-constrained hardware: Orin handles control and Thor performs model inference, supporting closed-loop tasks, scheduling experiments and consistent performance evaluation.

<div class="capability-values">

| Dimension | Capability |
| --- | --- |
| **Functionality** | Closes the observation–inference–execution loop with synchronous, asynchronous replacement and asynchronous blending modes. |
| **Responsiveness** | Overlaps inference with action execution to reduce the impact of prediction waits on control updates. |
| **Practicality** | Places the complete model on Thor, reducing the model memory and compute required on the Orin control device. |
| **Stability** | Aligns action timestamps, discards stale actions and handles empty buffers to limit disruptions caused by response latency. |
| **Safety** | Validates messages, action values and response identity to reduce the risk of invalid or mismatched data entering the control loop. |
| **Consistency** | Uses a common model interface and action semantics for checking local/remote outputs and comparing scheduling modes. |
| **Reproducibility** | Preserves configurations, random seeds and raw records for repeatable tasks and verifiable comparisons. |
| **Observability** | Records inference, communication, control timings and buffer state to locate bottlenecks and assess scheduling. |
| **Maintainability** | Separates model, transport and scheduling responsibilities for independent debugging and iteration. |
| **Extensibility** | Provides model and task interfaces for extending compression strategies, scheduling configurations and task scenarios. |

</div>

## Operating conditions

split v1 uses LIBERO relative-action control. The configured 20 Hz rate is an upper bound; actual cadence is measured from timestamps. A timeout or request error ends the experiment and records its status. See [deployment](./deployment.md) for dependencies and [validation](./validation.md) for memory and timing definitions.

The current client supports HTTP only. Use a controlled experimental network. Cross-network inference requires TLS, authentication and access controls, or an explicitly configured protected tunnel; changing the URL to `https://` alone is not supported by the current CLI.

`request_id` and `server_id` check consistency, not authorization. The tensor protocol avoids network pickle deserialization; model files must still come from trusted sources.

Physical robot operation requires an independent communication watchdog, velocity/workspace limits, collision protection and emergency stop. Zero-increment hold commands do not replace these controls.

## Validation sequence

Check task success and output consistency first, then latency and buffer behavior, followed by sustained operation and resource monitoring. Preserve configurations, device environments and raw results at each stage.
