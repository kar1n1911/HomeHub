# HomeHub demonstration plan (5-10 minutes)

1. Introduce HomeHub and the user problem.
2. Show the repository boundaries and architecture diagram.
3. Explain each REST service and its owned data.
4. Show the four Docker Hub images.
5. Explain the CNPG operator and generated per-service Secrets, then deploy with `kubectl apply -k kubernetes/` (or `kubernetes-local/` for a single-node demonstration).
6. Show pods, Services, HPA resources, and the database PVC.
7. Open HomeHub from outside Kubernetes and exercise each feature.
8. Scale one API independently and show the additional pods.
9. Delete an API pod and show Kubernetes restoring it.
10. Create a task through the REST API; show three database instances and separate PVCs, remove the primary Pod, then show a different primary and the retained task. State the single-node demonstration limit.
11. Show API and database logs and briefly walk through the Cluster, database roles, API probes, and Service YAML.
12. Close with benefits, challenges, and security improvements.


## Device signal demonstration (0.2.0)

Keep the complete recording within 5–10 minutes. After the task workflow, add a device using the browser, show its sampling interval, expand the delivered JSON, and refresh. Explain that the sample adapter is simulated and physical producers can push UUID-tagged readings.

Show `kubectl get deployment,scaledobject,hpa -n homehub`. Explain that the collector remains running while delivery workers can scale to zero. Use the saved signal-scaling verification record or run the local fault-injection script: stop the receiver, submit readings, show queue growth and four workers, restore the receiver, and show receipt of all IDs and scale-to-zero. Explain leases, acknowledgement after commit, deduplication, and why this is at-least-once delivery. Briefly show `kubernetes/config/signal-scaling.yaml` and state the single-node/storage/security limits.
