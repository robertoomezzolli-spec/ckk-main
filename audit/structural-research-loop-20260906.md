# First completed loop protocol

The loop completed five scheduled iterations and stopped at the node budget in
the fifth. Every exported partial or complete graph passed operator replay and
seed-rooted reachability. No source file changed during the loop.

| Iteration | Leaf/depth bounds | Nodes | Applications | Result |
| --- | --- | ---: | ---: | --- |
| 1 | 2 / 2 | 212 | 924 | Bounded saturation |
| 2 | 3 / 3 | 2,116 | 12,196 | Bounded saturation |
| 3 | 3 / 4 | 2,628 | 14,756 | Bounded saturation |
| 4 | 3 / 5 | 2,628 | 14,756 | No state growth at this scope |
| 5 | 4 / 5 | 5,000 | 15,081 | Node budget reached; incomplete |

Iterations 1-4 preserve every previously reached state and contain their entire
paired compatible control. Iteration 5 adds 2,964 observed state IDs but omits
592 from iteration 4 and does not yet contain its complete compatible control.
Because it is truncated, these omissions are resource-censored, not a demonstrated
regression of the unbounded rules. The loop reports them explicitly.

The plateau in iteration 4 concerns state and event sets under a three-leaf
budget. It does not demonstrate that all structures or any complete natural domain
have been covered. Raising the leaf bound causes further growth.

Five coordinator tests passed: checkpoint continuation versus a fresh run,
protocol/corruption rejection, correct separation of saturation and resource
termination, safe node-budget stopping, and rejection of non-nested protocols.
The generator and its previously tested kernels were unchanged in this sprint.

The JSON checkpoint contains the complete protocol, source fingerprints, five
paired summaries and example backtraces. External evaluation was not run; the
readiness inventory and the missing gate are recorded separately. The loop has
finished and no background process remains active.
